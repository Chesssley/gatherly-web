document.addEventListener("DOMContentLoaded", () => {
  console.log("Gatherly Flask app initialized.");

  // US-01-01: 兴趣标签 chip 点击交互
  // 当前仅提供视觉反馈，实际筛选逻辑由 US-06 实现
  const tagChips = document.querySelectorAll(".tag-chip");
  if (tagChips.length > 0) {
    tagChips.forEach(chip => {
      chip.addEventListener("click", () => {
        tagChips.forEach(c => c.classList.remove("active"));
        chip.classList.add("active");
        // TODO: US-06 接入后端筛选
        console.log("Selected tag:", chip.dataset.tag);
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
