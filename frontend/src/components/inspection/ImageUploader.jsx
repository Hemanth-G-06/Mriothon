import React, { useState, useRef, useEffect } from 'react';
import { Upload, X, AlertCircle, CheckCircle2, RefreshCw } from 'lucide-react';
import { validateInspectionImage, validateBatchImages, IMAGE_CONSTRAINTS } from '../../utils/imageValidators';
import { formatFileSize } from '../../utils/formatters';

/**
 * ImageUploader Component
 *
 * Supports single or multi-file drag-and-drop image uploads with client-side
 * dimension, format, and file size validation.
 *
 * Props:
 * - multiple: boolean (default false)
 * - value: File[] | File | null (controlled state)
 * - onChange: (files: File[] | File | null, metadata?: any) => void
 * - disabled: boolean
 * - maxFiles: number (default 10 for batch)
 */
export default function ImageUploader({
  multiple = false,
  value,
  onChange,
  disabled = false,
  maxFiles = 10
}) {
  const [isDragging, setIsDragging] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validationError, setValidationError] = useState(null);
  const [previewItems, setPreviewItems] = useState([]);
  const previewItemsRef = useRef([]);
  const fileInputRef = useRef(null);
  const dragCounter = useRef(0);

  // Keep previewItemsRef always in sync with previewItems
  useEffect(() => {
    previewItemsRef.current = previewItems;
  }, [previewItems]);

  // Sync internal preview state if external value is cleared or empty
  useEffect(() => {
    if (!value || (Array.isArray(value) && value.length === 0)) {
      // Clean up existing object URLs to avoid memory leaks
      previewItemsRef.current.forEach((item) => {
        if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
      });
      setPreviewItems([]);
      previewItemsRef.current = [];
      setValidationError(null);
    }
  }, [value]);

  // Cleanup object URLs on unmount
  useEffect(() => {
    return () => {
      previewItemsRef.current.forEach((item) => {
        if (item.previewUrl) URL.revokeObjectURL(item.previewUrl);
      });
    };
  }, []);

  const processFiles = async (fileList) => {
    if (!fileList || fileList.length === 0) return;
    setValidating(true);
    setValidationError(null);

    const incomingArray = Array.from(fileList);

    if (multiple) {
      // MULTI-IMAGE / BATCH MODE: SEQUENTIAL APPEND LOGIC
      const currentItems = previewItemsRef.current;
      const currentCount = currentItems.length;

      // 1. Identify and filter duplicate files (by name, size, lastModified)
      const newFiles = [];
      const duplicateNames = [];

      for (const file of incomingArray) {
        const isDuplicate = currentItems.some(
          (item) =>
            item.name === file.name &&
            item.size === file.size &&
            (item.file?.lastModified === file.lastModified || !item.file?.lastModified)
        );
        if (isDuplicate) {
          duplicateNames.push(file.name);
        } else {
          newFiles.push(file);
        }
      }

      if (newFiles.length === 0) {
        setValidationError(
          `Image${duplicateNames.length > 1 ? 's' : ''} "${duplicateNames.join(', ')}" already added to this batch.`
        );
        setValidating(false);
        return;
      }

      // 2. Validate total batch capacity against maxFiles (10)
      const remainingSlots = maxFiles - currentCount;
      if (newFiles.length > remainingSlots) {
        setValidationError(
          `Batch limit exceeded: You have ${currentCount} image(s) selected and tried to add ${newFiles.length} more. The maximum allowed is ${maxFiles} images per batch (${remainingSlots} slot${remainingSlots === 1 ? '' : 's'} remaining).`
        );
        setValidating(false);
        return;
      }

      // 3. Validate each incoming image (format, size, dimensions)
      const validationResults = await Promise.all(
        newFiles.map(async (file) => {
          const res = await validateInspectionImage(file);
          return { file, ...res };
        })
      );

      const validFiles = validationResults.filter((r) => r.isValid);
      const invalidFiles = validationResults.filter((r) => !r.isValid);

      if (invalidFiles.length > 0) {
        const errorDescriptions = invalidFiles.map((inv) => `${inv.file.name}: ${inv.error}`).join(' | ');
        setValidationError(
          invalidFiles.length === newFiles.length
            ? errorDescriptions
            : `Some images could not be added: ${errorDescriptions}`
        );
      } else if (duplicateNames.length > 0) {
        setValidationError(`Added valid image(s). Note: "${duplicateNames.join(', ')}" was skipped as duplicate.`);
      }

      // 4. Append valid items to existing items without dropping previously selected images
      if (validFiles.length > 0) {
        const newItems = validFiles.map((v) => ({
          file: v.file,
          previewUrl: URL.createObjectURL(v.file),
          name: v.file.name,
          size: v.file.size,
          isValid: true,
          error: null,
          width: v.width,
          height: v.height
        }));

        setPreviewItems((prev) => {
          const updated = [...prev, ...newItems].slice(0, maxFiles);
          previewItemsRef.current = updated;
          onChange(updated.map((item) => item.file), updated);
          return updated;
        });
      }
    } else {
      // SINGLE FILE MODE (Preserve exact single-image functionality)
      const targetFile = incomingArray[0];
      const validation = await validateInspectionImage(targetFile);

      if (!validation.isValid) {
        setValidationError(validation.error);
        setPreviewItems([]);
        previewItemsRef.current = [];
        onChange(null, null);
      } else {
        const item = {
          file: targetFile,
          previewUrl: URL.createObjectURL(targetFile),
          name: targetFile.name,
          size: targetFile.size,
          isValid: true,
          error: null,
          width: validation.width,
          height: validation.height
        };
        setPreviewItems([item]);
        previewItemsRef.current = [item];
        onChange(targetFile, item);
      }
    }

    setValidating(false);
  };

  const handleDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (disabled) return;
    dragCounter.current += 1;
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setIsDragging(true);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (disabled) return;
    e.dataTransfer.dropEffect = 'copy';
    if (!isDragging) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current -= 1;
    if (dragCounter.current <= 0) {
      dragCounter.current = 0;
      setIsDragging(false);
    }
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current = 0;
    setIsDragging(false);
    if (disabled) return;

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      await processFiles(e.dataTransfer.files);
    }
  };

  const handleFileInputChange = async (e) => {
    if (e.target.files && e.target.files.length > 0) {
      await processFiles(e.target.files);
      // Reset input value to allow selecting same or additional files
      e.target.value = '';
    }
  };

  const handleRemoveItem = (index) => {
    setPreviewItems((prev) => {
      const itemToRemove = prev[index];
      if (itemToRemove?.previewUrl) {
        URL.revokeObjectURL(itemToRemove.previewUrl);
      }
      const updated = prev.filter((_, i) => i !== index);
      previewItemsRef.current = updated;

      if (multiple) {
        onChange(updated.map((u) => u.file), updated);
        if (updated.length === 0) setValidationError(null);
      } else {
        onChange(null, null);
        setValidationError(null);
      }
      return updated;
    });
  };

  const handleReplaceSingle = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  return (
    <div className="w-100">
      {/* Hidden Native File Input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png"
        multiple={multiple}
        onChange={handleFileInputChange}
        className="d-none"
        disabled={disabled}
      />

      {/* Validation Error Alert */}
      {validationError && (
        <div className="alert alert-danger py-2 small d-flex align-items-center justify-content-between mb-3">
          <div className="d-flex align-items-center gap-2">
            <AlertCircle size={16} className="text-danger flex-shrink-0" />
            <span>{validationError}</span>
          </div>
          <button
            type="button"
            className="btn btn-sm btn-link text-danger p-0 text-decoration-none"
            onClick={() => setValidationError(null)}
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Main Container Render Logic */}
      {previewItems.length === 0 ? (
        /* INITIAL EMPTY DROPZONE (Both Single and Batch mode when empty) */
        <div
          onDragEnter={handleDragEnter}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !disabled && fileInputRef.current?.click()}
          className={`card text-center p-4 p-md-5 border-2 border-dashed cursor-pointer transition-all ${
            isDragging
              ? 'border-primary bg-primary bg-opacity-10'
              : 'border-secondary border-opacity-25 bg-white hover-shadow'
          }`}
          style={{
            cursor: disabled ? 'not-allowed' : 'pointer',
            borderRadius: '10px',
            minHeight: '220px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          <div className="p-3 rounded-circle bg-light text-primary mb-3">
            <Upload size={32} />
          </div>

          <h6 className="fw-bold text-dark mb-1">
            {multiple ? 'Drag & drop inspection images here' : 'Drag & drop inspection image here'}
          </h6>
          <p className="text-muted small mb-3">
            or click to browse from your device
          </p>

          {/* Specifications Checklist */}
          <div
            className="p-2 px-3 rounded bg-light border small text-muted d-flex flex-wrap align-items-center justify-content-center gap-2"
            style={{ fontSize: '0.75rem' }}
          >
            <span className="d-flex align-items-center gap-1">
              <CheckCircle2 size={12} className="text-success" /> JPEG or PNG
            </span>
            <span>•</span>
            <span className="d-flex align-items-center gap-1">
              <CheckCircle2 size={12} className="text-success" /> Max 5 MiB
            </span>
            <span>•</span>
            <span className="d-flex align-items-center gap-1">
              <CheckCircle2 size={12} className="text-success" /> Min 64×64 to Max 4096×4096 px
            </span>
            {multiple && (
              <>
                <span>•</span>
                <span className="d-flex align-items-center gap-1 fw-semibold text-primary">
                  1–10 images per batch
                </span>
              </>
            )}
          </div>

          {validating && (
            <div className="mt-3 text-primary small d-flex align-items-center gap-2">
              <span className="spinner-border spinner-border-sm" />
              <span>Validating image dimensions and format...</span>
            </div>
          )}
        </div>
      ) : !multiple ? (
        /* SINGLE IMAGE PREVIEW - KEEP 100% UNTOUCHED */
        <div className="card card-industrial p-3 bg-white">
          <div className="row g-3 align-items-center">
            <div className="col-12 col-md-4 text-center">
              <div
                className="position-relative rounded overflow-hidden border bg-dark d-flex align-items-center justify-content-center"
                style={{ maxHeight: '200px', minHeight: '160px' }}
              >
                <img
                  src={previewItems[0].previewUrl}
                  alt={previewItems[0].name}
                  className="img-fluid"
                  style={{ maxHeight: '190px', objectFit: 'contain' }}
                />
              </div>
            </div>

            <div className="col-12 col-md-8">
              <div className="d-flex justify-content-between align-items-start mb-2">
                <div>
                  <h6 className="fw-bold text-dark mb-1 text-truncate" style={{ maxWidth: '300px' }}>
                    {previewItems[0].name}
                  </h6>
                  <span className="badge bg-success bg-opacity-10 text-success border border-success border-opacity-25 small">
                    <CheckCircle2 size={11} className="me-1 inline" /> Validated Image
                  </span>
                </div>
                <button
                  type="button"
                  className="btn btn-sm btn-outline-danger"
                  onClick={() => handleRemoveItem(0)}
                  disabled={disabled}
                  title="Remove image"
                >
                  <X size={15} />
                </button>
              </div>

              <div className="row g-2 text-muted small my-2 py-2 border-top border-bottom" style={{ fontSize: '0.8rem' }}>
                <div className="col-6">
                  <span className="text-secondary">File Size:</span>{' '}
                  <strong className="text-dark">{formatFileSize(previewItems[0].size)}</strong>
                </div>
                <div className="col-6">
                  <span className="text-secondary">Dimensions:</span>{' '}
                  <strong className="text-dark">
                    {previewItems[0].width} × {previewItems[0].height} px
                  </strong>
                </div>
              </div>

              <div className="d-flex gap-2 mt-3">
                <button
                  type="button"
                  className="btn btn-sm btn-outline-secondary d-flex align-items-center gap-1"
                  onClick={handleReplaceSingle}
                  disabled={disabled}
                >
                  <RefreshCw size={13} /> Replace Image
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* MULTI-IMAGE BATCH: PREVIEWS WITH PERMANENTLY ACTIVE DRAG-AND-DROP ZONE */
        <div
          onDragEnter={handleDragEnter}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`card card-industrial p-3 bg-white position-relative transition-all ${
            isDragging ? 'border-primary shadow' : ''
          }`}
        >
          {/* Header Bar */}
          <div className="d-flex align-items-center justify-content-between pb-2 mb-3 border-bottom">
            <div className="d-flex align-items-center gap-2">
              <span className="fw-bold text-dark small">Selected Images:</span>
              <span className="badge bg-primary">
                {previewItems.length} of {maxFiles} max
              </span>
              {previewItems.length < maxFiles ? (
                <span className="badge bg-light text-secondary border small">
                  {maxFiles - previewItems.length} slot{maxFiles - previewItems.length === 1 ? '' : 's'} remaining
                </span>
              ) : (
                <span className="badge bg-success bg-opacity-10 text-success border border-success border-opacity-25 small">
                  Batch Full (10/10)
                </span>
              )}
            </div>
            {previewItems.length < maxFiles && (
              <button
                type="button"
                className="btn btn-sm btn-outline-primary d-flex align-items-center gap-1"
                onClick={() => fileInputRef.current?.click()}
                disabled={disabled}
              >
                <Upload size={13} /> Browse Files
              </button>
            )}
          </div>

          {/* Validation Feedback in Progress */}
          {validating && (
            <div className="p-2 mb-3 rounded bg-primary bg-opacity-10 text-primary small d-flex align-items-center gap-2">
              <span className="spinner-border spinner-border-sm" />
              <span>Validating newly dropped image(s)...</span>
            </div>
          )}

          {/* Selected Images Previews Grid */}
          <div className="row g-2 mb-3">
            {previewItems.map((item, idx) => (
              <div key={idx} className="col-6 col-sm-4 col-md-3 col-xl-2">
                <div
                  className={`card h-100 p-2 position-relative border ${
                    item.isValid ? 'border-light-subtle' : 'border-danger'
                  }`}
                  style={{ fontSize: '0.75rem' }}
                >
                  <button
                    type="button"
                    className="btn btn-sm btn-danger position-absolute top-0 end-0 m-1 p-0 rounded-circle d-flex align-items-center justify-content-center"
                    style={{ width: 20, height: 20, zIndex: 2 }}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRemoveItem(idx);
                    }}
                    disabled={disabled}
                    title="Remove image"
                  >
                    <X size={12} />
                  </button>

                  <div
                    className="rounded bg-light d-flex align-items-center justify-content-center mb-1 overflow-hidden"
                    style={{ height: '80px' }}
                  >
                    <img
                      src={item.previewUrl}
                      alt={item.name}
                      style={{ maxHeight: '100%', maxWidth: '100%', objectFit: 'cover' }}
                    />
                  </div>

                  <div className="text-truncate fw-medium text-dark" title={item.name}>
                    {item.name}
                  </div>
                  <div className="text-muted d-flex justify-content-between" style={{ fontSize: '0.68rem' }}>
                    <span>{formatFileSize(item.size)}</span>
                    {item.width && <span>{item.width}×{item.height}</span>}
                  </div>
                  {!item.isValid && (
                    <div className="text-danger small mt-1" style={{ fontSize: '0.65rem' }}>
                      {item.error}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Sequential Dropzone: Stays Active After Every Drop Until Max Limit */}
          {previewItems.length < maxFiles ? (
            <div
              onClick={() => !disabled && fileInputRef.current?.click()}
              className={`p-3 rounded-2 text-center border-2 border-dashed transition-all cursor-pointer ${
                isDragging
                  ? 'border-primary bg-primary bg-opacity-10 text-primary'
                  : 'border-secondary border-opacity-25 bg-light text-muted hover-shadow'
              }`}
              style={{ cursor: disabled ? 'not-allowed' : 'pointer' }}
            >
              <div className="d-flex align-items-center justify-content-center gap-2 mb-1">
                <Upload size={18} className={isDragging ? 'text-primary' : 'text-secondary'} />
                <span className="fw-semibold small text-dark">
                  Drag & drop additional images here, or click to browse
                </span>
              </div>
              <div className="small text-muted" style={{ fontSize: '0.74rem' }}>
                Drop images one at a time or together &bull; {maxFiles - previewItems.length} slot{maxFiles - previewItems.length === 1 ? '' : 's'} remaining &bull; JPEG or PNG &bull; Max 5 MiB
              </div>
            </div>
          ) : (
            <div className="p-2 rounded bg-light border text-center text-muted small" style={{ fontSize: '0.75rem' }}>
              <CheckCircle2 size={13} className="text-success me-1 inline" />
              Maximum batch capacity reached (10 of 10 images). Remove an image to add more.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
