import axios from 'axios';

const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 300000,
});

export const generateImage = async (file, style, roomType) => {
  const formData = new FormData();
  formData.append('image', file);
  formData.append('style', style);
  if (roomType) formData.append('room_type', roomType);
  
  const response = await apiClient.post('/generate', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

/**
 * 异步生成图片
 */
export const generateImageAsync = async (imageFile, style, roomType) => {
  const formData = new FormData();
  formData.append('image', imageFile);
  formData.append('style', style);
  if (roomType) formData.append('room_type', roomType);

  const response = await apiClient.post('/generate-async', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
};

/**
 * 查询任务状态
 */
export const getTaskStatus = async (taskId) => {
  const response = await apiClient.get(`/task/${taskId}`);
  return response.data;
};

/**
 * 获取支持的装修风格列表
 */
export const getStyles = async () => {
  const response = await apiClient.get('/styles');
  return response.data;
};

/**
 * 获取房间类型列表
 */
export const getRoomTypes = async () => {
  const response = await apiClient.get('/room-types');
  return response.data;
};

export default apiClient;
