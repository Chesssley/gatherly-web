document.addEventListener("DOMContentLoaded", () => {
  const editor = document.querySelector("[data-avatar-editor]");
  if (!editor) {
    return;
  }

  const MAX_SOURCE_BYTES = 2 * 1024 * 1024;
  const MAX_AVATAR_BYTES = 2 * 1024 * 1024;
  const OUTPUT_SIZE = 512;
  const sourceInput = document.getElementById("avatar-source");
  const uploadInput = document.getElementById("avatar-file");
  const form = document.getElementById("profile-form");
  const canvas = editor.querySelector("[data-avatar-canvas]");
  const context = canvas.getContext("2d");
  const cropPanel = editor.querySelector("[data-avatar-crop-panel]");
  const zoomInput = editor.querySelector("[data-avatar-zoom]");
  const removeInput = editor.querySelector("[data-avatar-remove]");
  const errorText = editor.querySelector("[data-avatar-error]");
  const submitButton = form.querySelector('button[type="submit"]');
  const state = { image: null, baseScale: 1, zoom: 1, x: 0, y: 0, dragging: false, pointerX: 0, pointerY: 0 };

  const showError = (message = "") => {
    errorText.textContent = message;
    errorText.hidden = !message;
  };

  const dimensions = () => ({
    width: state.image.naturalWidth * state.baseScale * state.zoom,
    height: state.image.naturalHeight * state.baseScale * state.zoom,
  });

  const clampPosition = () => {
    const { width, height } = dimensions();
    state.x = Math.min(0, Math.max(canvas.width - width, state.x));
    state.y = Math.min(0, Math.max(canvas.height - height, state.y));
  };

  const draw = () => {
    if (!state.image) {
      return;
    }
    clampPosition();
    const { width, height } = dimensions();
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.drawImage(state.image, state.x, state.y, width, height);
  };

  const resetCrop = () => {
    state.baseScale = Math.max(canvas.width / state.image.naturalWidth, canvas.height / state.image.naturalHeight);
    state.zoom = 1;
    zoomInput.value = "1";
    const { width, height } = dimensions();
    state.x = (canvas.width - width) / 2;
    state.y = (canvas.height - height) / 2;
    draw();
  };

  sourceInput.addEventListener("change", () => {
    showError();
    uploadInput.value = "";
    const file = sourceInput.files && sourceInput.files[0];
    if (!file) {
      cropPanel.hidden = true;
      state.image = null;
      return;
    }
    if (file.size > MAX_SOURCE_BYTES) {
      sourceInput.value = "";
      cropPanel.hidden = true;
      showError("原图不能超过 2MB。");
      return;
    }
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      sourceInput.value = "";
      cropPanel.hidden = true;
      showError("请选择 JPEG、PNG 或 WebP 图片。");
      return;
    }

    const image = new Image();
    image.onload = () => {
      URL.revokeObjectURL(image.src);
      state.image = image;
      cropPanel.hidden = false;
      removeInput.checked = false;
      resetCrop();
    };
    image.onerror = () => {
      URL.revokeObjectURL(image.src);
      sourceInput.value = "";
      cropPanel.hidden = true;
      showError("无法读取这张图片，请选择其他文件。");
    };
    image.src = URL.createObjectURL(file);
  });

  removeInput.addEventListener("change", () => {
    if (!removeInput.checked) {
      return;
    }
    sourceInput.value = "";
    uploadInput.value = "";
    cropPanel.hidden = true;
    state.image = null;
    showError();
  });

  zoomInput.addEventListener("input", () => {
    const previousZoom = state.zoom;
    const centerX = (canvas.width / 2 - state.x) / previousZoom;
    const centerY = (canvas.height / 2 - state.y) / previousZoom;
    state.zoom = Number(zoomInput.value);
    state.x = canvas.width / 2 - centerX * state.zoom;
    state.y = canvas.height / 2 - centerY * state.zoom;
    draw();
  });

  canvas.addEventListener("pointerdown", event => {
    state.dragging = true;
    state.pointerX = event.clientX;
    state.pointerY = event.clientY;
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener("pointermove", event => {
    if (!state.dragging) {
      return;
    }
    state.x += event.clientX - state.pointerX;
    state.y += event.clientY - state.pointerY;
    state.pointerX = event.clientX;
    state.pointerY = event.clientY;
    draw();
  });
  canvas.addEventListener("pointerup", () => {
    state.dragging = false;
  });

  const canvasToBlob = (target, type, quality) => new Promise(resolve => target.toBlob(resolve, type, quality));

  const buildAvatar = async () => {
    const output = document.createElement("canvas");
    output.width = OUTPUT_SIZE;
    output.height = OUTPUT_SIZE;
    const outputContext = output.getContext("2d");
    outputContext.fillStyle = "#ffffff";
    outputContext.fillRect(0, 0, OUTPUT_SIZE, OUTPUT_SIZE);
    outputContext.drawImage(canvas, 0, 0, OUTPUT_SIZE, OUTPUT_SIZE);

    for (const quality of [0.86, 0.76, 0.66, 0.56]) {
      const blob = await canvasToBlob(output, "image/webp", quality);
      if (blob && blob.size <= MAX_AVATAR_BYTES) {
        return { blob, filename: "avatar.webp" };
      }
    }
    for (const quality of [0.82, 0.7, 0.58]) {
      const blob = await canvasToBlob(output, "image/jpeg", quality);
      if (blob && blob.size <= MAX_AVATAR_BYTES) {
        return { blob, filename: "avatar.jpg" };
      }
    }
    throw new Error("裁剪后的头像仍然过大，请选择细节较少的图片。");
  };

  form.addEventListener("submit", async event => {
    if (!state.image || uploadInput.files.length > 0) {
      return;
    }
    event.preventDefault();
    showError();
    submitButton.disabled = true;
    try {
      const avatar = await buildAvatar();
      const transfer = new DataTransfer();
      transfer.items.add(new File([avatar.blob], avatar.filename, { type: avatar.blob.type }));
      uploadInput.files = transfer.files;
      form.submit();
    } catch (error) {
      showError(error.message);
      submitButton.disabled = false;
    }
  });
});
