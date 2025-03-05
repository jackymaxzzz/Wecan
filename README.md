# AI网页系统分析工具

这是一个基于Python的工具，用于通过Chrome DevTools Protocol捕获和分析网页内容。

## 功能

- 连接到正在运行的Chrome浏览器
- 捕获整个网页的截图（会自动分片处理大型页面）
- 提取完整的HTML内容（过滤掉样式相关代码）
- 检测并提取页面中的热搜信息

## 使用方法

1. 以远程调试模式启动Chrome浏览器：
   ```
   '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' --remote-debugging-port=9222
   ```

2. 打开您想要分析的网页

3. 运行脚本：
   ```
   python app.py
   ```

4. 按照提示选择要分析的页面

## 要求

- Python 3.8+
- websockets库
- Pillow库（用于图像处理）

## 安装依赖

```
pip install websockets pillow
```
