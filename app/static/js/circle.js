document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".circle-image-grid img").forEach(image => {
    const removeUnavailableImage = () => {
      image.closest("a")?.remove();
    };

    image.addEventListener("error", removeUnavailableImage, { once: true });
    if (image.complete && image.naturalWidth === 0) {
      removeUnavailableImage();
    }
  });

  document.querySelectorAll("[data-reply-group]").forEach(group => {
    const toggle = group.querySelector(":scope > [data-replies-toggle]");
    const collapsedReplies = group.querySelectorAll(":scope > [data-reply-item][hidden]");
    if (!toggle || collapsedReplies.length === 0) {
      return;
    }

    const hiddenCount = Number(toggle.dataset.hiddenCount || collapsedReplies.length);
    toggle.addEventListener("click", () => {
      const shouldExpand = toggle.getAttribute("aria-expanded") !== "true";
      collapsedReplies.forEach(reply => {
        reply.hidden = !shouldExpand;
      });
      toggle.setAttribute("aria-expanded", String(shouldExpand));
      toggle.textContent = shouldExpand ? "收起回复" : `展开更多回复（${hiddenCount}）`;
    });
  });

  const scrollTabs = Array.from(document.querySelectorAll("[data-scroll-target]"));
  const setActiveTab = activeTab => {
    scrollTabs.forEach(tab => {
      tab.classList.toggle("is-active", tab === activeTab);
    });
  };

  scrollTabs.forEach(tab => {
    tab.addEventListener("click", () => {
      const target = document.getElementById(tab.dataset.scrollTarget);
      setActiveTab(tab);
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  });

  const filterToggle = document.querySelector("[data-events-filter-toggle]");
  const filterMenu = document.querySelector("[data-events-filter-menu]");
  const filterLabel = document.querySelector("[data-events-filter-label]");
  const setActivityFilter = value => {
    document.querySelectorAll("[data-events-list]").forEach(list => {
      list.classList.toggle("is-hidden", list.dataset.eventsList !== value);
    });
    document.querySelectorAll("[data-events-filter-option]").forEach(option => {
      const isActive = option.dataset.eventsFilterOption === value;
      option.classList.toggle("is-active", isActive);
      if (isActive && filterLabel) {
        filterLabel.textContent = option.textContent.trim();
      }
    });
    if (filterMenu && filterToggle) {
      filterMenu.hidden = true;
      filterToggle.setAttribute("aria-expanded", "false");
    }
  };

  if (filterToggle && filterMenu) {
    filterToggle.addEventListener("click", () => {
      const shouldOpen = filterMenu.hidden;
      filterMenu.hidden = !shouldOpen;
      filterToggle.setAttribute("aria-expanded", String(shouldOpen));
    });
  }

  document.querySelectorAll("[data-events-filter-option]").forEach(option => {
    option.addEventListener("click", () => {
      setActivityFilter(option.dataset.eventsFilterOption);
    });
  });

  document.addEventListener("click", event => {
    if (
      filterMenu &&
      filterToggle &&
      !filterMenu.hidden &&
      !filterMenu.contains(event.target) &&
      !filterToggle.contains(event.target)
    ) {
      filterMenu.hidden = true;
      filterToggle.setAttribute("aria-expanded", "false");
    }
  });

  const memberModal = document.querySelector("[data-member-modal]");
  const openMemberModal = () => {
    if (!memberModal) {
      return;
    }
    memberModal.hidden = false;
    document.body.classList.add("circle-modal-open");
  };
  const closeMemberModal = () => {
    if (!memberModal) {
      return;
    }
    memberModal.hidden = true;
    document.body.classList.remove("circle-modal-open");
  };

  document.querySelectorAll("[data-member-modal-open]").forEach(button => {
    button.addEventListener("click", openMemberModal);
  });
  document.querySelectorAll("[data-member-modal-close]").forEach(button => {
    button.addEventListener("click", closeMemberModal);
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && memberModal && !memberModal.hidden) {
      closeMemberModal();
    }
  });
});
