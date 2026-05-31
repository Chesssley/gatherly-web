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

    const hiddenCount = collapsedReplies.length;
    toggle.addEventListener("click", () => {
      const shouldExpand = toggle.getAttribute("aria-expanded") !== "true";
      collapsedReplies.forEach(reply => {
        reply.hidden = !shouldExpand;
      });
      toggle.setAttribute("aria-expanded", String(shouldExpand));
      toggle.textContent = shouldExpand ? "收起回复" : `展开更多回复（${hiddenCount}）`;
    });
  });
});
