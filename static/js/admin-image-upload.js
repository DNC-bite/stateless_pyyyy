"use strict";

document.querySelectorAll("[data-image-upload]").forEach((upload) => {
    const input = upload.querySelector(".image-upload-input");
    const dropzone = upload.querySelector(".image-dropzone");
    const preview = upload.querySelector("[data-image-preview]");
    const image = upload.querySelector("[data-preview-image]");
    const status = upload.querySelector("[data-image-status]");
    let previewUrl = null;

    const showPreview = (file) => {
        if (!file) return;
        if (file.type && !file.type.startsWith("image/")) {
            status.textContent = "El archivo debe ser una imagen.";
            return;
        }
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        previewUrl = URL.createObjectURL(file);
        image.src = previewUrl;
        image.hidden = false;
        preview.hidden = false;
        status.textContent = file.name;
    };

    input.addEventListener("change", () => showPreview(input.files[0]));
    dropzone.addEventListener("dragover", (event) => {
        event.preventDefault();
        dropzone.classList.add("is-dragging");
    });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("is-dragging"));
    dropzone.addEventListener("drop", (event) => {
        event.preventDefault();
        dropzone.classList.remove("is-dragging");
        if (!event.dataTransfer.files.length) return;
        input.files = event.dataTransfer.files;
        input.dispatchEvent(new Event("change", { bubbles: true }));
    });
});
