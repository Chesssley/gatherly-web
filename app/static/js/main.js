document.addEventListener("DOMContentLoaded", () => {
  console.log("Gatherly Flask app initialized.");

  const flashMessages = document.querySelectorAll(".flash-msg, .flash-message");
  flashMessages.forEach(message => {
    window.setTimeout(() => {
      const removeMessage = () => {
        if (!message.isConnected) {
          return;
        }
        const container = message.closest(".flash-messages");
        message.remove();
        if (container && !container.querySelector(".flash-msg, .flash-message")) {
          container.remove();
        }
      };

      message.classList.add("is-fading");
      message.addEventListener("transitionend", removeMessage, { once: true });
      window.setTimeout(removeMessage, 600);
    }, 3000);
  });

  // UI-05: Meetup 风格分类导航和时间筛选。
  const discoverySection = document.querySelector(".discover-section");
  const categoryLinks = discoverySection?.querySelectorAll("[data-category]") || [];
  const timeFilters = discoverySection?.querySelectorAll("[data-time-filter]") || [];
  const discoveryCards = discoverySection?.querySelectorAll(".discover-card") || [];
  const filterParams = new URLSearchParams(window.location.search);
  const requestedCategory = filterParams.get("category") || "all";
  const requestedTime = filterParams.get("time") || "any";
  let activeCategory = Array.from(categoryLinks).some(link => link.dataset.category === requestedCategory)
    ? requestedCategory
    : "all";
  let activeTime = Array.from(timeFilters).some(filter => filter.dataset.timeFilter === requestedTime)
    ? requestedTime
    : "any";

  const syncFilterUrl = () => {
    const url = new URL(window.location.href);
    if (activeCategory === "all") {
      url.searchParams.delete("category");
    } else {
      url.searchParams.set("category", activeCategory);
    }
    if (activeTime === "any") {
      url.searchParams.delete("time");
    } else {
      url.searchParams.set("time", activeTime);
    }
    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
  };

  const updateFilterStatus = () => {
    const filterStatus = discoverySection?.querySelector(".filter-status");
    if (!filterStatus) {
      return;
    }

    const activeCategoryLink = discoverySection.querySelector(`[data-category="${activeCategory}"]`);
    const activeTimeFilter = discoverySection.querySelector(`[data-time-filter="${activeTime}"]`);
    const categoryLabel = activeCategoryLink?.textContent.trim() || "全部活动";
    const timeLabel = activeTimeFilter?.textContent.trim() || "全部时间";
    filterStatus.innerHTML = "";
    filterStatus.appendChild(document.createTextNode(`当前正在浏览：${categoryLabel} · ${timeLabel}`));

    if (activeCategory !== "all" || activeTime !== "any") {
      const clearLink = document.createElement("a");
      clearLink.href = "#";
      clearLink.className = "clear-filter-link";
      clearLink.textContent = "查看全部活动 / 清除筛选";
      clearLink.addEventListener("click", event => {
        event.preventDefault();
        activeCategory = "all";
        activeTime = "any";
        categoryLinks.forEach(item => item.classList.toggle("is-active", item.dataset.category === "all"));
        timeFilters.forEach(item => item.classList.toggle("is-active", item.dataset.timeFilter === "any"));
        syncFilterUrl();
        applyActivityFilters();
      });
      filterStatus.appendChild(clearLink);
    }
  };

  const applyActivityFilters = () => {
    let visibleCount = 0;
    discoveryCards.forEach(card => {
      const tags = (card.dataset.tags || "").split(",").map(tag => tag.trim());
      const time = card.dataset.time || "any";
      const categoryLink = discoverySection.querySelector(`[data-category="${activeCategory}"]`);
      const categoryTags = (categoryLink?.dataset.filterTags || "").split(",").filter(Boolean);
      const categoryMatches = activeCategory === "all"
        || categoryTags.length === 0
        || categoryTags.some(tag => tags.includes(tag));
      const timeMatches = activeTime === "any"
        || time === activeTime
        || (activeTime === "week" && ["today", "tomorrow", "week", "weekend"].includes(time));
      const isVisible = categoryMatches && timeMatches;
      card.style.display = isVisible ? "" : "none";
      if (isVisible) {
        visibleCount += 1;
      }
    });

    const noMatchTip = discoverySection?.querySelector(".no-match-tip");
    if (noMatchTip) {
      noMatchTip.hidden = visibleCount > 0;
    }
    updateFilterStatus();
  };

  categoryLinks.forEach(link => {
    link.addEventListener("click", event => {
      event.preventDefault();
      activeCategory = link.dataset.category || "all";
      categoryLinks.forEach(item => item.classList.toggle("is-active", item === link));
      syncFilterUrl();
      applyActivityFilters();
    });
  });

  timeFilters.forEach(filter => {
    filter.addEventListener("click", event => {
      event.preventDefault();
      activeTime = filter.dataset.timeFilter || "any";
      timeFilters.forEach(item => item.classList.toggle("is-active", item === filter));
      syncFilterUrl();
      applyActivityFilters();
    });
  });

  categoryLinks.forEach(item => item.classList.toggle("is-active", item.dataset.category === activeCategory));
  timeFilters.forEach(item => item.classList.toggle("is-active", item.dataset.timeFilter === activeTime));
  syncFilterUrl();
  applyActivityFilters();

  const showShareToast = (message) => {
    let toast = document.querySelector(".share-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.className = "share-toast";
      toast.setAttribute("role", "status");
      toast.setAttribute("aria-live", "polite");
      document.body.appendChild(toast);
    }

    toast.textContent = message;
    toast.classList.add("is-visible");
    window.clearTimeout(toast.hideTimer);
    toast.hideTimer = window.setTimeout(() => {
      toast.classList.remove("is-visible");
    }, 2200);
  };

  const copyTextFallback = (text) => {
    const input = document.createElement("textarea");
    input.value = text;
    input.setAttribute("readonly", "");
    input.style.position = "fixed";
    input.style.left = "-9999px";
    document.body.appendChild(input);
    input.select();

    let copied = false;
    try {
      copied = document.execCommand("copy");
    } finally {
      document.body.removeChild(input);
    }
    return copied ? Promise.resolve() : Promise.reject(new Error("copy failed"));
  };

  document.querySelectorAll(".circle-share-button[data-share-url], [data-activity-share][data-share-url]").forEach(button => {
    button.addEventListener("click", async () => {
      const shareUrl = new URL(button.dataset.shareUrl, window.location.origin).href;
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(shareUrl);
        } else {
          await copyTextFallback(shareUrl);
        }
        showShareToast("链接已复制");
      } catch (error) {
        showShareToast("复制失败，请手动复制链接");
      }
    });
  });

  document.querySelectorAll("[data-favorite-placeholder]").forEach(button => {
    button.addEventListener("click", () => {
      const isActive = button.classList.toggle("is-active");
      button.setAttribute("aria-pressed", String(isActive));
      button.querySelector("span").innerHTML = isActive ? "&#9829;" : "&#9825;";
      showShareToast(isActive ? "已添加到收藏预览" : "已取消收藏预览");
    });
  });

  const homeTabs = document.querySelectorAll("[data-home-tab]");
  const homeTabPanels = document.querySelectorAll("[data-home-tab-panel]");
  homeTabs.forEach(tab => {
    tab.addEventListener("click", () => {
      const selectedTab = tab.dataset.homeTab;
      homeTabs.forEach(item => {
        const isActive = item === tab;
        item.classList.toggle("is-active", isActive);
        item.setAttribute("aria-selected", String(isActive));
      });
      homeTabPanels.forEach(panel => {
        panel.hidden = panel.dataset.homeTabPanel !== selectedTab;
      });
    });
  });

  document.querySelectorAll("[data-login-required]").forEach(button => {
    button.addEventListener("click", () => {
      showShareToast("请先登录或注册后再参与互动");
    });
  });

  document.querySelectorAll("[data-comment-focus]").forEach(button => {
    button.addEventListener("click", () => {
      const target = document.getElementById(button.dataset.commentFocus);
      if (target) {
        target.focus();
        target.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    });
  });

  document.querySelectorAll("[data-reply-toggle]").forEach(button => {
    button.addEventListener("click", () => {
      const form = document.getElementById(button.dataset.replyToggle);
      if (!form) {
        return;
      }

      form.classList.toggle("is-hidden");
      const textarea = form.querySelector("textarea");
      if (!form.classList.contains("is-hidden") && textarea) {
        textarea.focus();
      }
    });
  });

  document.querySelectorAll("[data-image-upload][data-file-count-target]").forEach(input => {
    const target = document.getElementById(input.dataset.fileCountTarget);
    if (!target) {
      return;
    }

    input.addEventListener("change", () => {
      const files = input.files ? Array.from(input.files) : [];
      const maxCount = Number(input.dataset.maxCount || 0);
      const maxBytes = Number(input.dataset.maxBytes || 0);
      const oversizedFile = files.find(file => maxBytes && file.size > maxBytes);

      if (maxCount && files.length > maxCount) {
        window.alert(`最多只能选择 ${maxCount} 张图片。`);
        input.value = "";
      } else if (oversizedFile) {
        window.alert(`单张图片不能超过 ${Math.floor(maxBytes / 1024)}KB。`);
        input.value = "";
      }

      const count = input.files ? input.files.length : 0;
      target.textContent = count > 0 ? `已选择 ${count} 张图片` : "未选择图片";
    });
  });

  document.querySelectorAll("[data-member-picker]").forEach(picker => {
    const search = picker.querySelector("[data-member-search]");
    const members = picker.querySelectorAll("[data-member-item]");
    const emptyMessage = picker.querySelector("[data-member-empty]");
    if (!search) {
      return;
    }

    const filterMembers = () => {
      const query = search.value.trim().toLocaleLowerCase();
      let visibleCount = 0;
      members.forEach(member => {
        const searchText = (member.dataset.memberSearchText || "").toLocaleLowerCase();
        const isVisible = !query || searchText.includes(query);
        member.classList.toggle("is-hidden", !isVisible);
        if (isVisible) {
          visibleCount += 1;
        }
      });
      if (emptyMessage) {
        emptyMessage.classList.toggle("is-hidden", visibleCount > 0);
      }
    };

    search.addEventListener("input", filterMembers);
    filterMembers();
  });

  const togglePanel = (button, panel, shouldOpen) => {
    if (!button || !panel) {
      return;
    }

    button.setAttribute("aria-expanded", String(shouldOpen));
    panel.hidden = !shouldOpen;
  };

  const accountMenuButton = document.querySelector("[data-nav-menu-toggle]");
  const accountMenu = document.querySelector("[data-nav-menu]");
  const mobileSearchButton = document.querySelector("[data-mobile-search-toggle]");
  const mobileSearchPanel = document.querySelector("[data-mobile-search]");
  const mobileMenuButton = document.querySelector("[data-mobile-menu-toggle]");
  const mobileMenu = document.querySelector("[data-mobile-menu]");

  const closeNavigationPanels = () => {
    togglePanel(accountMenuButton, accountMenu, false);
    togglePanel(mobileSearchButton, mobileSearchPanel, false);
    togglePanel(mobileMenuButton, mobileMenu, false);
  };

  if (accountMenuButton && accountMenu) {
    accountMenuButton.addEventListener("click", event => {
      event.stopPropagation();
      const shouldOpen = accountMenu.hidden;
      closeNavigationPanels();
      togglePanel(accountMenuButton, accountMenu, shouldOpen);
    });
  }

  if (mobileSearchButton && mobileSearchPanel) {
    mobileSearchButton.addEventListener("click", event => {
      event.stopPropagation();
      const shouldOpen = mobileSearchPanel.hidden;
      closeNavigationPanels();
      togglePanel(mobileSearchButton, mobileSearchPanel, shouldOpen);
      if (shouldOpen) {
        mobileSearchPanel.querySelector("input")?.focus();
      }
    });
  }

  if (mobileMenuButton && mobileMenu) {
    mobileMenuButton.addEventListener("click", event => {
      event.stopPropagation();
      const shouldOpen = mobileMenu.hidden;
      closeNavigationPanels();
      togglePanel(mobileMenuButton, mobileMenu, shouldOpen);
    });
  }

  document.addEventListener("click", event => {
    if (!event.target.closest(".site-header")) {
      closeNavigationPanels();
    }
  });

  document.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      closeNavigationPanels();
    }
  });
});
