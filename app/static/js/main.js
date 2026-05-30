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

  // US-06-02: 兴趣标签 chip 点击 — 无刷新客户端筛选
  const tagChips = document.querySelectorAll(".interest-chip");
  if (tagChips.length > 0) {
    tagChips.forEach(chip => {
      chip.addEventListener("click", (e) => {
        e.preventDefault();

        const selectedTag = chip.dataset.tag;

        // 切换 active 状态
        tagChips.forEach(c => c.classList.remove("is-active"));
        chip.classList.add("is-active");

        // 筛选活动卡片
        const cards = document.querySelectorAll(".activity-card");
        if (selectedTag === "all") {
          cards.forEach(card => { card.style.display = ""; });
        } else {
          cards.forEach(card => {
            const tags = card.dataset.tags || "";
            if (tags.split(",").map(t => t.trim()).includes(selectedTag)) {
              card.style.display = "";
            } else {
              card.style.display = "none";
            }
          });
        }

        // 动态更新 filter-status 区域
        const filterStatus = document.querySelector(".filter-status");
        if (filterStatus) {
          if (selectedTag === "all") {
            filterStatus.innerHTML = "当前正在浏览：全部活动";
          } else {
            const clearLink = document.createElement("a");
            clearLink.href = "#";
            clearLink.textContent = "查看全部活动 / 清除筛选";
            clearLink.addEventListener("click", (ev) => {
              ev.preventDefault();
              const allChip = document.querySelector('.interest-chip[data-tag="all"]');
              if (allChip) allChip.click();
            });
            filterStatus.innerHTML = "";
            filterStatus.appendChild(document.createTextNode("当前正在浏览：" + selectedTag + "  "));
            filterStatus.appendChild(clearLink);
          }
        }

        // 无匹配结果提示
        let visibleCount = 0;
        cards.forEach(card => {
          if (card.style.display !== "none") visibleCount++;
        });
        const existingTip = document.querySelector(".no-match-tip");
        if (visibleCount === 0) {
          if (!existingTip) {
            const tip = document.createElement("p");
            tip.className = "no-match-tip";
            tip.textContent = "暂无匹配的活动，试试其他标签吧！";
            if (filterStatus) {
              filterStatus.insertAdjacentElement("afterend", tip);
            }
          }
        } else {
          if (existingTip) existingTip.remove();
        }
      });
    });
  }

  const tagToggle = document.querySelector("[data-tag-toggle]");
  if (tagToggle) {
    tagToggle.addEventListener("click", () => {
      const interestSection = tagToggle.closest(".interest-section");
      if (!interestSection) {
        return;
      }

      const isExpanded = interestSection.classList.toggle("is-expanded");
      tagToggle.setAttribute("aria-expanded", String(isExpanded));
      tagToggle.textContent = isExpanded ? "收起标签" : "展开更多兴趣";
    });
  }

  // US-06-03: 清除筛选链接 — 无刷新跳转到全部
  const clearFilterLink = document.querySelector(".clear-filter-link");
  if (clearFilterLink) {
    clearFilterLink.addEventListener("click", (e) => {
      e.preventDefault();
      // 点击"全部"标签，触发筛选切换
      const allChip = document.querySelector('.interest-chip[data-tag="all"]');
      if (allChip) {
        allChip.click();
      }
    });
  }

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

  document.querySelectorAll(".circle-share-button[data-share-url]").forEach(button => {
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

  document.querySelectorAll(".circle-file-input[data-file-count-target]").forEach(input => {
    const target = document.getElementById(input.dataset.fileCountTarget);
    if (!target) {
      return;
    }

    input.addEventListener("change", () => {
      const count = input.files ? input.files.length : 0;
      target.textContent = count > 0 ? `已选择 ${count} 张图片` : "未选择图片";
    });
  });
});
