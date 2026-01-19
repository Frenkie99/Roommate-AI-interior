import axios from 'axios';

const apiClient = axios.create({
  baseURL: '/api/v1/segment',
  timeout: 300000,
});

export const segmentByPoint = async (imageFile, x, y, label = 1) => {
  const formData = new FormData();
  formData.append('image', imageFile);
  formData.append('x', x);
  formData.append('y', y);
  formData.append('label', label);

  const response = await apiClient.post('/by-point', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const segmentByText = async (imageFile, text, threshold = 0.5) => {
  const formData = new FormData();
  formData.append('image', imageFile);
  formData.append('text', text);
  formData.append('threshold', threshold);

  const response = await apiClient.post('/by-text', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const segmentByBox = async (imageFile, x1, y1, x2, y2, label = 1) => {
  const formData = new FormData();
  formData.append('image', imageFile);
  formData.append('x1', x1);
  formData.append('y1', y1);
  formData.append('x2', x2);
  formData.append('y2', y2);
  formData.append('label', label);

  const response = await apiClient.post('/by-box', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const previewMask = async (imageFile, maskBase64, alpha = 128) => {
  const formData = new FormData();
  formData.append('image', imageFile);
  formData.append('mask_base64', maskBase64);
  formData.append('alpha', alpha);

  const response = await apiClient.post('/preview-mask', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const inpaintRegion = async (imageFile, maskBase64, prompt, negativePrompt = null, strength = 0.85) => {
  const formData = new FormData();
  formData.append('image', imageFile);
  formData.append('mask_base64', maskBase64);
  formData.append('prompt', prompt);
  if (negativePrompt) formData.append('negative_prompt', negativePrompt);
  formData.append('strength', strength);

  const response = await apiClient.post('/inpaint', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const replaceFurniture = async (imageFile, maskBase64, furnitureType, style = 'modern') => {
  const formData = new FormData();
  formData.append('image', imageFile);
  formData.append('mask_base64', maskBase64);
  formData.append('furniture_type', furnitureType);
  formData.append('style', style);

  const response = await apiClient.post('/replace-furniture', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const replaceDecoration = async (imageFile, maskBase64, decorationType, description = null) => {
  const formData = new FormData();
  formData.append('image', imageFile);
  formData.append('mask_base64', maskBase64);
  formData.append('decoration_type', decorationType);
  if (description) formData.append('description', description);

  const response = await apiClient.post('/replace-decoration', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

export const getFurnitureTypes = async () => {
  const response = await apiClient.get('/furniture-types');
  return response.data;
};

export const getDecorationTypes = async () => {
  const response = await apiClient.get('/decoration-types');
  return response.data;
};

export default apiClient;
