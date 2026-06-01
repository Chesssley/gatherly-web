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

  const initGlobalSearchSuggestions = () => {
    const forms = Array.from(document.querySelectorAll("[data-search-suggestions]"));
    if (!forms.length) {
      return;
    }

    const createStatus = (menu, message, isLoading = false) => {
      menu.textContent = "";
      const status = document.createElement("div");
      status.className = "search-suggestions-state";
      status.textContent = message;
      menu.appendChild(status);
      menu.hidden = false;
      menu.setAttribute("aria-busy", String(isLoading));
    };

    const itemInitial = (title) => Array.from((title || "").trim())[0]?.toUpperCase() || "G";

    forms.forEach((form, formIndex) => {
      const keywordInput = form.querySelector('input[name="q"]');
      if (!keywordInput) {
        return;
      }

      const cityInput = form.querySelector('input[name="city"]');
      const suggestionsUrl = form.dataset.suggestionsUrl || "/search/suggestions";
      const searchUrl = form.dataset.searchUrl || form.getAttribute("action") || "/search";
      const menu = document.createElement("div");
      menu.className = "search-suggestions-menu";
      menu.id = `search-suggestions-menu-${formIndex}`;
      menu.setAttribute("role", "listbox");
      menu.hidden = true;
      form.appendChild(menu);

      keywordInput.setAttribute("aria-autocomplete", "list");
      keywordInput.setAttribute("aria-controls", menu.id);
      keywordInput.setAttribute("aria-expanded", "false");

      let debounceTimer = null;
      let activeController = null;
      let requestSerial = 0;
      let lastRenderedQuery = "";

      const setMenuOpen = (isOpen) => {
        menu.hidden = !isOpen;
        keywordInput.setAttribute("aria-expanded", String(isOpen));
        if (!isOpen) {
          menu.removeAttribute("aria-busy");
        }
      };

      const closeMenu = () => {
        setMenuOpen(false);
      };

      const renderSection = (title, items, type) => {
        if (!Array.isArray(items) || !items.length) {
          return;
        }

        const section = document.createElement("section");
        section.className = "search-suggestions-section";
        const heading = document.createElement("h3");
        heading.textContent = title;
        section.appendChild(heading);

        const list = document.createElement("div");
        list.className = "search-suggestions-list";
        items.forEach(item => {
          const row = item.url ? document.createElement("a") : document.createElement("div");
          row.className = `search-suggestion-item search-suggestion-${type}`;
          row.setAttribute("role", "option");
          if (item.url) {
            row.href = item.url;
          }

          if (type === "user") {
            if (item.avatar) {
              const avatar = document.createElement("img");
              avatar.className = "search-suggestion-avatar";
              avatar.src = item.avatar;
              avatar.alt = "";
              row.appendChild(avatar);
            } else {
              const avatar = document.createElement("span");
              avatar.className = "search-suggestion-avatar search-suggestion-avatar-placeholder";
              avatar.textContent = itemInitial(item.title);
              avatar.setAttribute("aria-hidden", "true");
              row.appendChild(avatar);
            }
          }

          const text = document.createElement("span");
          text.className = "search-suggestion-text";
          const main = document.createElement("strong");
          main.textContent = item.title || "未命名";
          const subtitle = document.createElement("small");
          subtitle.textContent = item.subtitle || "";
          text.appendChild(main);
          if (subtitle.textContent) {
            text.appendChild(subtitle);
          }
          row.appendChild(text);
          list.appendChild(row);
        });

        section.appendChild(list);
        menu.appendChild(section);
      };

      const renderResults = (query, payload) => {
        if (keywordInput.value.trim() !== query) {
          return;
        }

        menu.textContent = "";
        menu.removeAttribute("aria-busy");
        renderSection("活动", payload.activities, "activity");
        renderSection("同好圈", payload.circles, "circle");
        renderSection("用户", payload.users, "user");
        const hasResults = Boolean(menu.children.length);
        if (!hasResults) {
          createStatus(menu, "未找到相关内容");
        } else {
          setMenuOpen(true);
        }
        lastRenderedQuery = query;
      };

      const fetchSuggestions = async (query) => {
        if (!query) {
          closeMenu();
          if (activeController) {
            activeController.abort();
          }
          return;
        }

        if (activeController) {
          activeController.abort();
        }
        activeController = new AbortController();
        const serial = requestSerial + 1;
        requestSerial = serial;
        createStatus(menu, "正在搜索...", true);

        const url = new URL(suggestionsUrl, window.location.origin);
        url.searchParams.set("q", query);
        try {
          const response = await fetch(url.toString(), {
            headers: { Accept: "application/json" },
            signal: activeController.signal,
          });
          if (!response.ok) {
            throw new Error("suggestion request failed");
          }
          const payload = await response.json();
          if (serial !== requestSerial) {
            return;
          }
          renderResults(query, payload || {});
        } catch (error) {
          if (error.name === "AbortError" || serial !== requestSerial) {
            return;
          }
          createStatus(menu, "未找到相关内容");
          lastRenderedQuery = query;
        }
      };

      const queueFetch = () => {
        const query = keywordInput.value.trim();
        window.clearTimeout(debounceTimer);
        if (!query) {
          closeMenu();
          return;
        }
        debounceTimer = window.setTimeout(() => fetchSuggestions(query), 250);
      };

      const navigateToSearch = () => {
        const query = keywordInput.value.trim();
        if (!query) {
          closeMenu();
          return false;
        }

        const url = new URL(searchUrl, window.location.origin);
        url.searchParams.set("q", query);
        const city = cityInput?.value.trim();
        if (city) {
          url.searchParams.set("city", city);
        }
        window.location.href = url.toString();
        return true;
      };

      keywordInput.addEventListener("input", queueFetch);
      keywordInput.addEventListener("focus", () => {
        const query = keywordInput.value.trim();
        if (!query) {
          return;
        }
        if (lastRenderedQuery === query && menu.children.length) {
          setMenuOpen(true);
          return;
        }
        fetchSuggestions(query);
      });
      keywordInput.addEventListener("keydown", event => {
        if (event.key === "Escape") {
          closeMenu();
        } else if (event.key === "Enter") {
          event.preventDefault();
          navigateToSearch();
        }
      });
      cityInput?.addEventListener("keydown", event => {
        if (event.key === "Enter") {
          event.preventDefault();
          navigateToSearch();
        } else if (event.key === "Escape") {
          closeMenu();
        }
      });

      form.addEventListener("submit", event => {
        event.preventDefault();
        navigateToSearch();
      });

      document.addEventListener("click", event => {
        if (!form.contains(event.target)) {
          closeMenu();
        }
      });
    });
  };

  initGlobalSearchSuggestions();

  const dismissedBannerKey = "gatherlyDiscoveryBannerDismissed";
  const isBannerDismissed = () => {
    try {
      if (window.localStorage?.getItem(dismissedBannerKey) === "1") {
        return true;
      }
    } catch (error) {
      // Fall through to the cookie check when localStorage is unavailable.
    }
    return document.cookie.split("; ").some(item => item === `${dismissedBannerKey}=1`);
  };
  const rememberBannerDismissed = () => {
    try {
      window.localStorage?.setItem(dismissedBannerKey, "1");
    } catch (error) {
      // Cookie fallback below keeps the dismissal persistent.
    }
    document.cookie = `${dismissedBannerKey}=1; max-age=31536000; path=/; SameSite=Lax`;
  };

  if (isBannerDismissed()) {
    document.querySelectorAll(".meetup-create-banner").forEach(banner => {
      banner.hidden = true;
    });
  }

  document.querySelectorAll("[data-banner-dismiss]").forEach(button => {
    button.addEventListener("click", event => {
      event.preventDefault();
      event.stopPropagation();
      const banner = button.closest(".meetup-create-banner");
      if (banner) {
        banner.hidden = true;
        rememberBannerDismissed();
      }
    });
  });

  // UI-05: Meetup 风格分类导航和时间筛选。
  const discoverySection = document.querySelector(".discover-section");
  const categoryLinks = discoverySection?.querySelectorAll("[data-category]") || [];
  const timeFilters = discoverySection?.querySelectorAll("[data-time-filter]") || [];
  const typeFilters = discoverySection?.querySelectorAll("[data-activity-type-filter]") || [];
  const discoveryCards = discoverySection?.querySelectorAll(".discover-card") || [];
  const filterParams = new URLSearchParams(window.location.search);
  const requestedCategory = filterParams.get("category") || "all";
  const requestedTime = filterParams.get("time") || "any";
  const requestedType = filterParams.get("type") || "any";
  let activeCategory = Array.from(categoryLinks).some(link => link.dataset.category === requestedCategory)
    ? requestedCategory
    : "all";
  let activeTime = Array.from(timeFilters).some(filter => filter.dataset.timeFilter === requestedTime)
    ? requestedTime
    : "any";
  let activeType = Array.from(typeFilters).some(filter => filter.dataset.activityTypeFilter === requestedType)
    ? requestedType
    : "any";

  const syncFilterUrl = () => {
    if (!discoverySection) {
      return;
    }
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
    if (activeType === "any") {
      url.searchParams.delete("type");
    } else {
      url.searchParams.set("type", activeType);
    }
    window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);

    discoverySection?.querySelectorAll("[data-preserve-filter-link]").forEach(link => {
      const linkUrl = new URL(link.dataset.baseHref || link.getAttribute("href") || window.location.href, window.location.origin);
      if (activeCategory === "all") {
        linkUrl.searchParams.delete("category");
      } else {
        linkUrl.searchParams.set("category", activeCategory);
      }
      if (activeTime === "any") {
        linkUrl.searchParams.delete("time");
      } else {
        linkUrl.searchParams.set("time", activeTime);
      }
      if (activeType === "any") {
        linkUrl.searchParams.delete("type");
      } else {
        linkUrl.searchParams.set("type", activeType);
      }
      link.setAttribute("href", `${linkUrl.pathname}${linkUrl.search}${linkUrl.hash}`);
    });
  };

  const updateFilterStatus = () => {
    const filterStatus = discoverySection?.querySelector(".filter-status");
    if (!filterStatus) {
      return;
    }
    filterStatus.innerHTML = "";
    filterStatus.hidden = true;

    if (activeCategory !== "all" || activeTime !== "any") {
      const clearLink = document.createElement("a");
      clearLink.href = "#";
      clearLink.className = "clear-filter-link";
      clearLink.textContent = "查看全部活动 / 清除筛选";
      clearLink.addEventListener("click", event => {
        event.preventDefault();
        activeCategory = "all";
        activeTime = "any";
        activeType = "any";
        categoryLinks.forEach(item => item.classList.toggle("is-active", item.dataset.category === "all"));
        timeFilters.forEach(item => item.classList.toggle("is-active", item.dataset.timeFilter === "any"));
        typeFilters.forEach(item => item.classList.toggle("is-active", item.dataset.activityTypeFilter === "any"));
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
      const activityType = card.dataset.activityType || "offline";
      const categoryLink = discoverySection.querySelector(`[data-category="${activeCategory}"]`);
      const categoryTags = (categoryLink?.dataset.filterTags || "").split(",").filter(Boolean);
      const categoryMatches = activeCategory === "all"
        || categoryTags.length === 0
        || categoryTags.some(tag => tags.includes(tag));
      const timeMatches = activeTime === "any"
        || time === activeTime
        || (activeTime === "week" && ["today", "tomorrow", "week", "weekend"].includes(time));
      const typeMatches = activeType === "any" || activityType === activeType;
      const isVisible = categoryMatches && timeMatches && typeMatches;
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
      if (link.getAttribute("href") && link.getAttribute("href") !== "#") {
        return;
      }
      event.preventDefault();
      activeCategory = link.dataset.category || "all";
      categoryLinks.forEach(item => item.classList.toggle("is-active", item === link));
      syncFilterUrl();
      applyActivityFilters();
    });
  });

  timeFilters.forEach(filter => {
    filter.addEventListener("click", event => {
      if (filter.getAttribute("href") && filter.getAttribute("href") !== "#") {
        return;
      }
      event.preventDefault();
      activeTime = filter.dataset.timeFilter || "any";
      timeFilters.forEach(item => item.classList.toggle("is-active", item === filter));
      const filterMenu = filter.closest("[data-home-date-filter]");
      if (filterMenu) {
        const toggle = filterMenu.querySelector("[data-home-date-toggle]");
        const popover = filterMenu.querySelector("[data-home-date-popover]");
        if (toggle) {
          const label = filter.textContent.trim();
          toggle.firstChild.textContent = `${label} `;
          toggle.setAttribute("aria-expanded", "false");
        }
        if (popover) {
          popover.hidden = true;
        }
      }
      syncFilterUrl();
      applyActivityFilters();
    });
  });

  typeFilters.forEach(filter => {
    filter.addEventListener("click", event => {
      event.preventDefault();
      activeType = filter.dataset.activityTypeFilter || "any";
      typeFilters.forEach(item => item.classList.toggle("is-active", item === filter));
      const filterMenu = filter.closest(".meetup-filter-menu");
      if (filterMenu) {
        const toggle = filterMenu.querySelector("[data-activity-type-toggle]");
        const popover = filterMenu.querySelector("[data-activity-type-popover]");
        if (toggle) {
          const label = filter.textContent.trim();
          toggle.firstChild.textContent = `${label} `;
          toggle.setAttribute("aria-expanded", "false");
        }
        if (popover) {
          popover.hidden = true;
        }
      }
      syncFilterUrl();
      applyActivityFilters();
    });
  });

  categoryLinks.forEach(item => item.classList.toggle("is-active", item.dataset.category === activeCategory));
  timeFilters.forEach(item => item.classList.toggle("is-active", item.dataset.timeFilter === activeTime));
  typeFilters.forEach(item => item.classList.toggle("is-active", item.dataset.activityTypeFilter === activeType));
  const initialActiveTypeFilter = Array.from(typeFilters).find(item => item.dataset.activityTypeFilter === activeType);
  if (initialActiveTypeFilter) {
    const filterMenu = initialActiveTypeFilter.closest(".meetup-filter-menu");
    const toggle = filterMenu?.querySelector("[data-activity-type-toggle]");
    if (toggle) {
      toggle.firstChild.textContent = `${initialActiveTypeFilter.textContent.trim()} `;
    }
  }
  syncFilterUrl();
  applyActivityFilters();

  document.querySelectorAll("[data-activity-type-toggle]").forEach(toggle => {
    const filterMenu = toggle.closest(".meetup-filter-menu");
    const popover = filterMenu?.querySelector("[data-activity-type-popover]");
    if (!popover) {
      return;
    }

    toggle.addEventListener("click", event => {
      event.preventDefault();
      event.stopPropagation();
      const willOpen = popover.hidden;
      document.querySelectorAll("[data-activity-type-popover]").forEach(item => {
        item.hidden = true;
      });
      popover.hidden = !willOpen;
      toggle.setAttribute("aria-expanded", String(willOpen));
    });

    popover.addEventListener("click", event => {
      event.stopPropagation();
    });
  });

  document.querySelectorAll("[data-home-date-filter]").forEach(filter => {
    const toggle = filter.querySelector("[data-home-date-toggle]");
    const popover = filter.querySelector("[data-home-date-popover]");
    if (!toggle || !popover) {
      return;
    }

    toggle.addEventListener("click", event => {
      event.preventDefault();
      event.stopPropagation();
      const willOpen = popover.hidden;
      document.querySelectorAll("[data-home-date-popover]").forEach(item => {
        item.hidden = true;
      });
      popover.hidden = !willOpen;
      toggle.setAttribute("aria-expanded", String(willOpen));
    });

    popover.addEventListener("click", event => {
      event.stopPropagation();
    });

    popover.querySelectorAll("[data-home-date-day]").forEach(dayButton => {
      dayButton.addEventListener("click", event => {
        event.preventDefault();
        event.stopPropagation();
        if (dayButton.disabled) {
          return;
        }
        popover.querySelectorAll("[data-home-date-day]").forEach(item => {
          item.classList.remove("is-selected");
          item.setAttribute("aria-pressed", "false");
        });
        dayButton.classList.add("is-selected");
        dayButton.setAttribute("aria-pressed", "true");
        const label = dayButton.dataset.homeDateLabel || dayButton.textContent.trim();
        toggle.firstChild.textContent = `${label} `;
        popover.hidden = true;
        toggle.setAttribute("aria-expanded", "false");
      });
    });
  });

  document.addEventListener("click", () => {
    document.querySelectorAll("[data-home-date-filter]").forEach(filter => {
      const toggle = filter.querySelector("[data-home-date-toggle]");
      const popover = filter.querySelector("[data-home-date-popover]");
      if (toggle && popover) {
        popover.hidden = true;
        toggle.setAttribute("aria-expanded", "false");
      }
    });
    document.querySelectorAll("[data-activity-type-popover]").forEach(popover => {
      popover.hidden = true;
      popover.closest(".meetup-filter-menu")?.querySelector("[data-activity-type-toggle]")?.setAttribute("aria-expanded", "false");
    });
  });

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

  const syncFavoriteButtons = (activityId, isFavorited) => {
    document.querySelectorAll(`[data-activity-favorite][data-activity-id="${activityId}"]`).forEach(button => {
      button.classList.toggle("is-active", isFavorited);
      button.setAttribute("aria-pressed", String(isFavorited));
      const icon = button.querySelector("span[aria-hidden='true']");
      const label = button.querySelector("[data-favorite-label]");
      if (icon) {
        icon.innerHTML = isFavorited ? "&#9829;" : "&#9825;";
      }
      if (label) {
        label.textContent = isFavorited ? "已收藏" : "收藏活动";
      }
    });
  };

  document.querySelectorAll("[data-activity-favorite]").forEach(button => {
    button.addEventListener("click", async event => {
      event.preventDefault();
      event.stopPropagation();
      if (!button.dataset.favoriteUrl) {
        return;
      }

      button.disabled = true;
      try {
        const response = await fetch(button.dataset.favoriteUrl, {
          method: "POST",
          headers: { Accept: "application/json" },
        });
        const result = await response.json();
        if (response.status === 401 && result.login_url) {
          showShareToast("请先登录后再收藏活动");
          window.setTimeout(() => {
            window.location.href = result.login_url;
          }, 500);
          return;
        }
        if (!response.ok) {
          throw new Error(result.error || "favorite request failed");
        }

        syncFavoriteButtons(button.dataset.activityId, result.is_favorited);
        showShareToast(result.is_favorited ? "已收藏活动" : "已取消收藏");
      } catch (error) {
        showShareToast("收藏操作失败，请稍后重试");
      } finally {
        button.disabled = false;
      }
    });
  });

  document.querySelectorAll("[data-card-url]").forEach(card => {
    const openCard = event => {
      if (event.target.closest("button, a, input, select, textarea")) {
        return;
      }
      window.location.href = card.dataset.cardUrl;
    };

    card.addEventListener("click", openCard);
    card.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openCard(event);
      }
    });
  });

  const initHorizontalCardScroller = ({
    carouselSelector,
    trackSelector,
    previousSelector,
    nextSelector,
    cardSelector,
  }) => {
    document.querySelectorAll(carouselSelector).forEach(carousel => {
      const strip = carousel.querySelector(trackSelector);
      const previousButton = carousel.querySelector(previousSelector);
      const nextButton = carousel.querySelector(nextSelector);
      if (!strip || !previousButton || !nextButton) {
        return;
      }

      const updateCarouselButtons = () => {
        const maxScrollLeft = Math.max(0, strip.scrollWidth - strip.clientWidth);
        previousButton.disabled = strip.scrollLeft <= 1;
        nextButton.disabled = strip.scrollLeft >= maxScrollLeft - 1;
      };

      const scrollFeaturedCards = direction => {
        const firstCard = strip.querySelector(cardSelector);
        const gap = Number.parseFloat(window.getComputedStyle(strip).columnGap || "0") || 0;
        const scrollDistance = firstCard ? firstCard.offsetWidth + gap : strip.clientWidth;
        strip.scrollBy({ left: direction * scrollDistance, behavior: "smooth" });
      };

      previousButton.addEventListener("click", () => scrollFeaturedCards(-1));
      nextButton.addEventListener("click", () => scrollFeaturedCards(1));
      strip.addEventListener("scroll", updateCarouselButtons, { passive: true });
      window.addEventListener("resize", updateCarouselButtons);
      updateCarouselButtons();
    });
  };

  initHorizontalCardScroller({
    carouselSelector: "[data-recommended-carousel]",
    trackSelector: "[data-recommended-track]",
    previousSelector: "[data-recommended-previous]",
    nextSelector: "[data-recommended-next]",
    cardSelector: ".recommended-card, .home-event-card",
  });

  initHorizontalCardScroller({
    carouselSelector: "[data-featured-carousel]",
    trackSelector: "[data-featured-strip]",
    previousSelector: "[data-featured-previous]",
    nextSelector: "[data-featured-next]",
    cardSelector: ".featured-card",
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

  document.querySelectorAll("[data-organizer-banner-dismiss]").forEach(button => {
    button.addEventListener("click", () => {
      button.closest("[data-organizer-banner]")?.remove();
    });
  });

  document.querySelectorAll("[data-cancel-reason]").forEach(select => {
    const form = select.closest("form");
    const customReason = form?.querySelector("[data-custom-reason]");
    const customReasonLabel = form?.querySelector("[data-custom-reason-label]");
    const syncCustomReason = () => {
      const isOther = select.value === "other";
      if (customReason) {
        customReason.hidden = !isOther;
        customReason.required = isOther;
        if (!isOther) {
          customReason.value = "";
        }
      }
      if (customReasonLabel) {
        customReasonLabel.hidden = !isOther;
      }
    };

    select.addEventListener("change", syncCustomReason);
    syncCustomReason();
  });

  document.querySelectorAll("[data-admin-status-menu]").forEach(select => {
    const originalValue = select.value;
    select.addEventListener("change", () => {
      if (!select.value || select.value === originalValue) {
        return;
      }
      if (select.value === "cancelled") {
        const confirmMessage = select.dataset.cancelConfirm || "确定取消这个活动吗？";
        if (!window.confirm(confirmMessage)) {
          select.value = originalValue;
          return;
        }
      }
      const form = select.closest("form");
      if (typeof form?.requestSubmit === "function") {
        form.requestSubmit();
      } else {
        form?.submit();
      }
    });
  });

  document.querySelectorAll("[data-activity-timezone]").forEach(input => {
    if (!input.value) {
      input.value = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    }
  });

  document.querySelectorAll("[data-peer-review-list]").forEach(list => {
    const items = Array.from(list.querySelectorAll("[data-peer-review-item]"));
    items.forEach(item => {
      item.addEventListener("toggle", () => {
        if (!item.open) {
          return;
        }
        items.forEach(otherItem => {
          if (otherItem !== item) {
            otherItem.open = false;
          }
        });
      });
    });
  });

  const myEventsSearch = document.querySelector("[data-my-events-search]");
  const myEventsSearchToggle = myEventsSearch?.querySelector("[data-my-events-search-toggle]");
  const myEventsSearchField = myEventsSearch?.querySelector("[data-my-events-search-field]");
  const myEventsSearchInput = myEventsSearch?.querySelector("[data-my-events-search-input]");

  const toggleMyEventsSearch = (shouldOpen) => {
    if (!myEventsSearch || !myEventsSearchToggle || !myEventsSearchField) {
      return;
    }

    myEventsSearch.classList.toggle("is-open", shouldOpen);
    myEventsSearchToggle.setAttribute("aria-expanded", String(shouldOpen));
    myEventsSearchField.hidden = !shouldOpen;
    if (shouldOpen) {
      myEventsSearchInput?.focus();
    }
  };

  if (myEventsSearchToggle && myEventsSearchField) {
    myEventsSearchToggle.addEventListener("click", () => {
      const shouldOpen = !myEventsSearch.classList.contains("is-open");
      if (!shouldOpen && myEventsSearchInput?.value.trim()) {
        myEventsSearchInput.focus();
        return;
      }
      toggleMyEventsSearch(shouldOpen);
    });
  }

  const togglePanel = (button, panel, shouldOpen) => {
    if (!button || !panel) {
      return;
    }

    button.setAttribute("aria-expanded", String(shouldOpen));
    panel.hidden = !shouldOpen;
  };

  const accountActionButtons = Array.from(document.querySelectorAll("[data-account-action-toggle]"));
  const accountActionPanels = Array.from(document.querySelectorAll("[data-account-action-panel]"));
  accountActionButtons.forEach(button => {
    const panel = document.getElementById(button.dataset.accountActionToggle);
    if (!panel || !accountActionPanels.includes(panel)) {
      return;
    }

    button.addEventListener("click", () => {
      const shouldOpen = panel.hidden;
      accountActionPanels.forEach(item => {
        item.hidden = item === panel ? !shouldOpen : true;
      });
      accountActionButtons.forEach(item => {
        item.setAttribute("aria-expanded", String(item === button && shouldOpen));
      });
    });
  });

  const accountMenuButtons = Array.from(document.querySelectorAll("[data-nav-menu-toggle]"));
  const accountMenus = Array.from(document.querySelectorAll("[data-nav-menu]"));
  const mobileSearchButton = document.querySelector("[data-mobile-search-toggle]");
  const mobileSearchPanel = document.querySelector("[data-mobile-search]");
  const mobileMenuButton = document.querySelector("[data-mobile-menu-toggle]");
  const mobileMenu = document.querySelector("[data-mobile-menu]");

  const closeNavigationPanels = () => {
    accountMenuButtons.forEach(button => {
      const menu = document.getElementById(button.getAttribute("aria-controls"));
      togglePanel(button, menu, false);
    });
    togglePanel(mobileSearchButton, mobileSearchPanel, false);
    togglePanel(mobileMenuButton, mobileMenu, false);
  };

  accountMenuButtons.forEach(button => {
    const menu = document.getElementById(button.getAttribute("aria-controls"));
    if (!menu || !accountMenus.includes(menu)) {
      return;
    }

    button.addEventListener("click", event => {
      event.stopPropagation();
      const shouldOpen = menu.hidden;
      closeNavigationPanels();
      togglePanel(button, menu, shouldOpen);
    });
  });

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
      if (!myEventsSearchInput?.value.trim()) {
        toggleMyEventsSearch(false);
      }
    }
  });
});
