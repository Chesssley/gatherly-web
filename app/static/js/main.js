document.addEventListener("DOMContentLoaded", () => {
  console.log("Gatherly Flask app initialized.");

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
        if (selectedTag === "全部活动") {
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
          if (selectedTag === "全部活动") {
            filterStatus.innerHTML = "当前正在浏览：全部活动";
          } else {
            const clearLink = document.createElement("a");
            clearLink.href = "#";
            clearLink.textContent = "查看全部活动 / 清除筛选";
            clearLink.addEventListener("click", (ev) => {
              ev.preventDefault();
              const allChip = document.querySelector('.interest-chip[data-tag="全部活动"]');
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
});
