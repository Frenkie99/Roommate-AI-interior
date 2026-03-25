# 部署说明 - 登录/注册功能更新

## 📋 更新内容
- ✅ 合并登录/注册按钮为单个"登录/注册"按钮
- ✅ 新增 AuthModal 弹窗组件
- ✅ 左侧室内设计背景图 + 产品logo展示
- ✅ 右侧手机号+验证码+密码登录表单
- ✅ 表单验证、错误提示、加载状态
- ✅ 验证码60秒倒计时功能
- ✅ authService API 服务封装

## 🚀 部署步骤

### 方法1: 使用部署脚本（推荐）
```bash
# Linux/Mac
./deploy.sh

# Windows
deploy.bat
```

### 方法2: 手动部署
1. **构建前端**
   ```bash
   cd frontend
   npm run build
   ```

2. **上传文件到服务器**
   - 将 `frontend/dist/` 目录下的所有文件
   - 上传到服务器的 `/var/www/roommate/frontend/` 目录

3. **重启nginx**
   ```bash
   ssh root@47.76.239.100
   systemctl reload nginx
   ```

## 🌐 访问地址
- **生产环境**: https://roommate-ai.cn/
- **服务器IP**: http://47.76.239.100/

## 🔍 测试功能
1. 访问网站，点击右上角"登录/注册"按钮
2. 验证弹窗是否正常显示
3. 测试表单验证功能
4. 测试验证码倒计时
5. 测试登录/注册切换

## 📁 构建文件位置
```
frontend/dist/
├── index.html
├── assets/
│   ├── index-CXaeHRyi.css
│   ├── index-DDPLjf31.js
│   └── interior-design-bg.jpg
└── logo/
    └── 导航栏logo-抠图.png
```

## ⚠️ 注意事项
- 确保服务器上的 `/var/www/roommate/frontend/` 目录权限正确
- 上传前建议备份当前版本
- 如有问题，可回滚到备份版本
