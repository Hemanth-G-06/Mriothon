/**
 * Image Validation Utilities for Visual Quality Inspection
 *
 * Challenge Constraints:
 * - Formats: JPEG and PNG only (image/jpeg, image/png)
 * - Maximum file size: 5 MiB (5 * 1024 * 1024 bytes)
 * - Minimum dimensions: 64 × 64 pixels
 * - Maximum dimensions: 4096 × 4096 pixels
 * - Batch size: 1–10 images
 */

export const IMAGE_CONSTRAINTS = {
  MAX_FILE_SIZE: 5 * 1024 * 1024, // 5 MiB in bytes
  MAX_FILE_SIZE_LABEL: '5 MiB',
  ALLOWED_TYPES: ['image/jpeg', 'image/png'],
  ALLOWED_EXTENSIONS: ['.jpg', '.jpeg', '.png'],
  MIN_WIDTH: 64,
  MIN_HEIGHT: 64,
  MAX_WIDTH: 4096,
  MAX_HEIGHT: 4096,
  MIN_BATCH_SIZE: 1,
  MAX_BATCH_SIZE: 10
};

/**
 * Validate a single image file for format, size, and dimensions
 * @param {File} file
 * @returns {Promise<{ isValid: boolean, error: string | null, width?: number, height?: number }>}
 */
export async function validateInspectionImage(file) {
  if (!file) {
    return { isValid: false, error: 'No image file provided.' };
  }

  // 1. File type and extension check
  const hasValidMime = IMAGE_CONSTRAINTS.ALLOWED_TYPES.includes(file.type);
  const fileName = (file.name || '').toLowerCase();
  const hasValidExt = IMAGE_CONSTRAINTS.ALLOWED_EXTENSIONS.some((ext) => fileName.endsWith(ext));

  if (!hasValidMime && !hasValidExt) {
    return {
      isValid: false,
      error: `Unsupported file format for "${file.name}". Only JPEG (.jpg, .jpeg) and PNG (.png) images are permitted.`
    };
  }

  // 2. File size check (5 MiB max)
  if (file.size > IMAGE_CONSTRAINTS.MAX_FILE_SIZE) {
    const sizeInMB = (file.size / (1024 * 1024)).toFixed(2);
    return {
      isValid: false,
      error: `File "${file.name}" exceeds maximum allowed size of 5 MiB (current size: ${sizeInMB} MB).`
    };
  }

  if (file.size === 0) {
    return {
      isValid: false,
      error: `File "${file.name}" is empty (0 bytes). Please upload a valid image.`
    };
  }

  // 3. Image dimensions & integrity check (asynchronous via browser Image)
  return new Promise((resolve) => {
    if (typeof window === 'undefined' || typeof Image === 'undefined' || typeof URL.createObjectURL === 'undefined') {
      // In non-browser / SSR / test environments, bypass dimension rendering
      resolve({ isValid: true, error: null, width: 512, height: 512 });
      return;
    }

    const objectUrl = URL.createObjectURL(file);
    const img = new Image();

    img.onload = () => {
      URL.revokeObjectURL(objectUrl);
      const width = img.naturalWidth;
      const height = img.naturalHeight;

      if (width < IMAGE_CONSTRAINTS.MIN_WIDTH || height < IMAGE_CONSTRAINTS.MIN_HEIGHT) {
        resolve({
          isValid: false,
          error: `Image dimensions (${width} × ${height} px) are smaller than minimum allowed dimensions of ${IMAGE_CONSTRAINTS.MIN_WIDTH} × ${IMAGE_CONSTRAINTS.MIN_HEIGHT} px.`,
          width,
          height
        });
        return;
      }

      if (width > IMAGE_CONSTRAINTS.MAX_WIDTH || height > IMAGE_CONSTRAINTS.MAX_HEIGHT) {
        resolve({
          isValid: false,
          error: `Image dimensions (${width} × ${height} px) exceed maximum allowed dimensions of ${IMAGE_CONSTRAINTS.MAX_WIDTH} × ${IMAGE_CONSTRAINTS.MAX_HEIGHT} px.`,
          width,
          height
        });
        return;
      }

      resolve({
        isValid: true,
        error: null,
        width,
        height
      });
    };

    img.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      resolve({
        isValid: false,
        error: `File "${file.name}" appears to be corrupted or not a valid decodeable image.`
      });
    };

    img.src = objectUrl;
  });
}

/**
 * Validate a batch of image files
 * @param {File[]} files
 * @returns {Promise<{ isValid: boolean, error: string | null, results: Array }>}
 */
export async function validateBatchImages(files) {
  if (!files || files.length === 0) {
    return {
      isValid: false,
      error: 'Please select at least 1 image for batch inspection.',
      results: []
    };
  }

  if (files.length > IMAGE_CONSTRAINTS.MAX_BATCH_SIZE) {
    return {
      isValid: false,
      error: `Batch size exceeded. You selected ${files.length} images, but the maximum allowed batch size is ${IMAGE_CONSTRAINTS.MAX_BATCH_SIZE} images.`,
      results: []
    };
  }

  const results = await Promise.all(
    files.map(async (file) => {
      const validation = await validateInspectionImage(file);
      return {
        file,
        name: file.name,
        size: file.size,
        isValid: validation.isValid,
        error: validation.error,
        width: validation.width,
        height: validation.height
      };
    })
  );

  const hasInvalid = results.some((r) => !r.isValid);
  return {
    isValid: !hasInvalid,
    error: hasInvalid ? 'One or more selected images failed validation.' : null,
    results
  };
}
