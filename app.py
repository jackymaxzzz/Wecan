import websockets
import json
import asyncio
import time
import os

async def capture_content():
    try:
        print("尝试连接到Chrome DevTools Protocol...")
        
        # 获取可用页面列表
        import urllib.request
        pages = []
        selected_page = None
        
        try:
            with urllib.request.urlopen('http://localhost:9222/json') as response:
                pages = json.loads(response.read().decode())
                print("可用的Chrome页面:")
                
                for i, page in enumerate(pages):
                    print(f"[{i+1}] 标题: {page.get('title', '无标题')[:50]}...")
                    print(f"    URL: {page.get('url', '无URL')[:50]}...")
                
                # 添加用户选择功能
                while True:
                    try:
                        choice = input("\n请输入数字选择要捕获的页面 (1-{0}): ".format(len(pages)))
                        choice_idx = int(choice) - 1
                        
                        if 0 <= choice_idx < len(pages):
                            selected_page = pages[choice_idx]
                            print(f"\n您选择了: {selected_page.get('title', '无标题')}")
                            print(f"URL: {selected_page.get('url', '无URL')}")
                            break
                        else:
                            print(f"请输入1到{len(pages)}之间的数字")
                    except ValueError:
                        print("请输入有效的数字")
                        
        except Exception as e:
            print(f"无法获取页面列表: {e}")
            print("将使用默认值继续")
        
        # 连接到特定页面
        if selected_page:
            page_id = selected_page.get('id')
            websocket_url = selected_page.get('webSocketDebuggerUrl')
            if not websocket_url:
                websocket_url = f"ws://localhost:9222/devtools/page/{page_id}"
        else:
            page_id = "7ED949C28E281D1F94AA04EBA14808E5"  # 默认值
            websocket_url = f"ws://localhost:9222/devtools/page/{page_id}"
            
        print(f"正在连接到页面: {websocket_url}")
        
        async with websockets.connect(websocket_url, ping_interval=None) as ws:
            print("连接成功!")
            
            # 获取页面标题
            await ws.send(json.dumps({
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": "document.title"
                }
            }))
            
            response = await ws.recv()
            data = json.loads(response)
            print("\n页面标题响应:", data)
            
            # 获取页面URL用于命名文件
            await ws.send(json.dumps({
                "id": 2,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": "window.location.hostname || window.location.href.split('/')[2]"
                }
            }))
            
            response = await ws.recv()
            data = json.loads(response)
            url_hostname = data.get('result', {}).get('result', {}).get('value', 'unknown')
            # 清理URL，使其适合作为文件名
            url_hostname = ''.join(c if c.isalnum() or c in '-_.' else '_' for c in url_hostname)
            
            # 获取页面URL
            await ws.send(json.dumps({
                "id": 3,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": "window.location.href"
                }
            }))
            
            response = await ws.recv()
            data = json.loads(response)
            print("\n页面URL响应:", data)
            
            # 获取简单的页面信息
            await ws.send(json.dumps({
                "id": 4,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": "JSON.stringify({links: document.links.length, images: document.images.length, forms: document.forms.length})"
                }
            }))
            
            response = await ws.recv()
            data = json.loads(response)
            print("\n页面元素数量响应:", data)
            
            # 提取有用信息
            print("\n==== 页面信息摘要 ====")
            try:
                if "result" in data and "result" in data["result"] and "value" in data["result"]["result"]:
                    info = json.loads(data["result"]["result"]["value"])
                    print(f"链接数量: {info.get('links', '未知')}")
                    print(f"图片数量: {info.get('images', '未知')}")
                    print(f"表单数量: {info.get('forms', '未知')}")
            except Exception as e:
                print(f"解析页面信息时出错: {e}")
            
            # 创建截图目录
            screenshots_dir = "screenshots"
            os.makedirs(screenshots_dir, exist_ok=True)
            
            # 步骤1: 获取完整页面尺寸
            print("\n获取页面完整尺寸...")
            await ws.send(json.dumps({
                "id": 5,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": "JSON.stringify({width: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth), height: Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)})"
                }
            }))
            
            size_response = await ws.recv()
            size_data = json.loads(size_response)
            
            try:
                if "result" in size_data and "result" in size_data["result"] and "value" in size_data["result"]["result"]:
                    size_info = json.loads(size_data["result"]["result"]["value"])
                    page_width = size_info.get("width", 1024)
                    page_height = size_info.get("height", 768)
                    print(f"页面尺寸: {page_width}x{page_height}像素")
                else:
                    # 默认值
                    page_width = 1024
                    page_height = 768
                    print(f"无法获取页面尺寸，使用默认值: {page_width}x{page_height}像素")
            except Exception as e:
                # 默认值
                page_width = 1024
                page_height = 768
                print(f"解析页面尺寸时出错: {e}")
                print(f"使用默认值: {page_width}x{page_height}像素")
            
            # 步骤2: 设置视口尺寸为页面尺寸
            print("\n设置视口尺寸...")
            await ws.send(json.dumps({
                "id": 6,
                "method": "Emulation.setDeviceMetricsOverride",
                "params": {
                    "width": page_width,
                    "height": page_height,
                    "deviceScaleFactor": 1,
                    "mobile": False
                }
            }))
            
            viewport_response = await ws.recv()
            print("视口设置响应:", json.loads(viewport_response))
            
            # 步骤3: 分片捕获完整页面，避免消息过大
            # 创建时间戳文件夹存储所有分片
            timestamp = int(time.time())
            fragment_dir = os.path.join(screenshots_dir, f"{url_hostname}_{timestamp}")
            os.makedirs(fragment_dir, exist_ok=True)
            
            # 确定分片大小和数量
            fragment_height = 1000  # 每个分片的高度
            num_fragments = (page_height + fragment_height - 1) // fragment_height  # 向上取整
            
            print(f"\n将页面分为{num_fragments}个分片进行截图...")
            
            all_fragments = []
            for i in range(num_fragments):
                y_position = i * fragment_height
                height = min(fragment_height, page_height - y_position)
                
                if height <= 0:
                    break
                
                print(f"\n截取分片 {i+1}/{num_fragments}... (从Y={y_position}, 高度={height})")
                
                # 使用较低质量进行分片截图
                await ws.send(json.dumps({
                    "id": 7 + i,
                    "method": "Page.captureScreenshot",
                    "params": {
                        "format": "jpeg",
                        "quality": 80,
                        "clip": {
                            "x": 0,
                            "y": y_position,
                            "width": page_width,
                            "height": height,
                            "scale": 1
                        }
                    }
                }))
                
                fragment_response = await ws.recv()
                fragment_data = json.loads(fragment_response)
                
                if "result" in fragment_data and "data" in fragment_data["result"]:
                    import base64
                    fragment_base64 = fragment_data["result"]["data"]
                    fragment_binary = base64.b64decode(fragment_base64)
                    
                    fragment_filename = os.path.join(fragment_dir, f"fragment_{i+1}.jpg")
                    with open(fragment_filename, "wb") as f:
                        f.write(fragment_binary)
                    
                    print(f"分片 {i+1} 已保存: {fragment_filename}")
                    print(f"分片大小: {len(fragment_binary) / 1024:.2f} KB")
                    
                    all_fragments.append(fragment_filename)
                else:
                    print(f"获取分片 {i+1} 失败:", fragment_data)
            
            # 尝试合并分片（可选）
            if all_fragments:
                try:
                    # 检查是否有PIL库
                    from PIL import Image
                    
                    full_image = None
                    total_height = 0
                    
                    # 首先确定完整尺寸
                    for filename in all_fragments:
                        with Image.open(filename) as img:
                            if full_image is None:
                                width = img.width
                                total_height += img.height
                            else:
                                total_height += img.height
                    
                    # 创建新图像
                    full_image = Image.new('RGB', (width, total_height))
                    
                    # 拼接各个部分
                    y_offset = 0
                    for filename in all_fragments:
                        with Image.open(filename) as img:
                            full_image.paste(img, (0, y_offset))
                            y_offset += img.height
                    
                    # 保存完整图像（可以降低质量以减小文件大小）
                    merged_filename = os.path.join(screenshots_dir, f"{url_hostname}_{timestamp}.jpg")
                    full_image.save(merged_filename, 'JPEG', quality=85)
                    
                    print(f"\n已将所有分片合并为一个完整的截图: {merged_filename}")
                    print(f"完整截图尺寸: {width}x{total_height}像素")
                    
                    # 获取文件大小
                    file_size = os.path.getsize(merged_filename) / 1024  # KB
                    print(f"完整截图文件大小: {file_size:.2f} KB")
                    
                except ImportError:
                    print("\n无法合并分片：缺少PIL库。")
                    print("可以通过运行 'pip install pillow' 安装PIL库，然后手动合并分片。")
                    print(f"所有分片已保存到: {fragment_dir}")
                except Exception as e:
                    print(f"\n合并分片时出错: {e}")
                    import traceback
                    traceback.print_exc()
                    print(f"所有分片已保存到: {fragment_dir}")
            
            # 步骤4: 重置视口设置
            print("\n重置视口设置...")
            await ws.send(json.dumps({
                "id": 100,
                "method": "Emulation.clearDeviceMetricsOverride"
            }))
            
            reset_response = await ws.recv()
            print("视口重置响应:", json.loads(reset_response))
            
            # 获取完整HTML源码（分片获取，避免消息太大）
            print("\n开始获取HTML源码...")
            
            # 使用具体的JavaScript代码块来分片获取HTML
            chunk_size = 100000  # 每个分片的大小（字符数）
            
            # 第一步：获取HTML总长度
            await ws.send(json.dumps({
                "id": 101,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": "document.documentElement.outerHTML.length"
                }
            }))
            
            length_response = await ws.recv()
            length_data = json.loads(length_response)
            
            try:
                html_length = length_data.get('result', {}).get('result', {}).get('value', 0)
                print(f"HTML源码总长度: {html_length} 字符")
                
                # 直接分片获取HTML，而不是先将整个HTML存储在JavaScript变量中
                print(f"需要 {(html_length + chunk_size - 1) // chunk_size} 个分片来获取完整HTML")
                
                # 分片获取HTML
                all_html_chunks = []
                chunks_needed = (html_length + chunk_size - 1) // chunk_size
                
                for i in range(chunks_needed):
                    start_index = i * chunk_size
                    end_index = min((i + 1) * chunk_size, html_length)
                    
                    print(f"获取分片 {i+1}/{chunks_needed} (字符 {start_index} 到 {end_index})...")
                    
                    # 直接从document.documentElement.outerHTML获取指定范围的内容
                    await ws.send(json.dumps({
                        "id": 102 + i,
                        "method": "Runtime.evaluate",
                        "params": {
                            "expression": f"document.documentElement.outerHTML.substring({start_index}, {end_index})"
                        }
                    }))
                    
                    chunk_response = await ws.recv()
                    chunk_data = json.loads(chunk_response)
                    chunk = chunk_data.get('result', {}).get('result', {}).get('value', '')
                    
                    all_html_chunks.append(chunk)
                    print(f"获取到 {len(chunk)} 字符")
                
                # 合并所有分片
                full_html = ''.join(all_html_chunks)
                
                # 过滤掉样式代码
                print("\n正在过滤样式代码...")
                await ws.send(json.dumps({
                    "id": 300,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": """
                        (function() {
                            // 创建一个临时的DOM解析器
                            const parser = new DOMParser();
                            const doc = parser.parseFromString(document.documentElement.outerHTML, 'text/html');
                            
                            // 移除所有style标签
                            const styles = doc.querySelectorAll('style');
                            for (const style of styles) {
                                style.parentNode.removeChild(style);
                            }
                            
                            // 移除所有link标签中的CSS
                            const cssLinks = doc.querySelectorAll('link[rel="stylesheet"], link[type*="css"]');
                            for (const link of cssLinks) {
                                link.parentNode.removeChild(link);
                            }
                            
                            // 移除所有script标签中可能包含样式操作的脚本
                            const scripts = doc.querySelectorAll('script');
                            for (const script of scripts) {
                                const scriptContent = script.textContent || script.innerText;
                                // 移除可能包含样式操作的脚本
                                if (scriptContent && (
                                    scriptContent.includes('style') || 
                                    scriptContent.includes('css') || 
                                    scriptContent.includes('classList') ||
                                    scriptContent.includes('.class') ||
                                    scriptContent.includes('animation')
                                )) {
                                    script.parentNode.removeChild(script);
                                }
                            }
                            
                            // 移除所有元素的style属性和class属性
                            const allElements = doc.querySelectorAll('*');
                            for (const el of allElements) {
                                el.removeAttribute('style');
                                el.removeAttribute('class');
                                // 移除其他可能与样式相关的属性
                                el.removeAttribute('data-styles');
                                el.removeAttribute('data-styled');
                                el.removeAttribute('data-emotion');
                                el.removeAttribute('data-theme');
                            }
                            
                            // 移除head中的其他可能与样式相关的元素
                            const head = doc.querySelector('head');
                            if (head) {
                                const meta = head.querySelectorAll('meta[name*="theme"], meta[name*="color"]');
                                meta.forEach(m => m.parentNode.removeChild(m));
                            }
                            
                            return new XMLSerializer().serializeToString(doc);
                        })();
                        """
                    }
                }))
                
                try:
                    filtered_response = await ws.recv()
                    filtered_data = json.loads(filtered_response)
                    filtered_html = filtered_data.get('result', {}).get('result', {}).get('value', '')
                    
                    # 使用过滤后的HTML，如果过滤失败则使用原始HTML
                    if filtered_html and len(filtered_html) > 0:
                        print(f"样式过滤成功，HTML大小从 {len(full_html)/1024:.2f} KB 减少到 {len(filtered_html)/1024:.2f} KB")
                        full_html = filtered_html
                    else:
                        print("样式过滤失败，使用原始HTML")
                except Exception as e:
                    print(f"样式过滤时出错: {e}")
                    print("使用原始HTML继续")
                
                # 保存完整HTML到文件
                html_dir = "html_source"
                os.makedirs(html_dir, exist_ok=True)
                timestamp = int(time.time())
                
                # 获取页面URL并转换为有效的文件名
                await ws.send(json.dumps({
                    "id": 301,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": "window.location.hostname || window.location.href.split('/')[2]"
                    }
                }))
                
                url_response = await ws.recv()
                url_data = json.loads(url_response)
                url_hostname = url_data.get('result', {}).get('result', {}).get('value', 'unknown')
                
                # 提取主机名并清理不适合文件名的字符
                url_hostname = ''.join(c if c.isalnum() or c in '-_.' else '_' for c in url_hostname)
                
                html_filename = os.path.join(html_dir, f"{url_hostname}_{timestamp}.html")
                with open(html_filename, "w", encoding="utf-8") as f:
                    f.write(full_html)
                
                print(f"\nHTML源码已保存至: {html_filename}")
                print(f"HTML源码大小: {len(full_html) / 1024:.2f} KB")
                
                # 打印HTML源码的前2000个字符和后1000个字符作为预览
                print("\nHTML源码预览 (前2000个字符):")
                print("="*80)
                print(full_html[:2000])
                print("="*80)
                print("\n... [中间内容省略] ...\n")
                print("="*80)
                print("\nHTML源码预览 (后1000个字符):")
                print(full_html[-1000:])
                print("="*80)
                
                # 执行JavaScript从页面中直接提取热搜信息
                print("\n尝试提取热搜信息...")
                await ws.send(json.dumps({
                    "id": 400,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": """
                        (function() {
                            // 尝试各种可能的热搜选择器
                            let hotItems = [];
                            
                            // 通用方法：查找包含"热搜"的元素
                            const hotElements = Array.from(document.querySelectorAll('*')).filter(el => 
                                el.textContent.includes('热搜') && 
                                el.querySelectorAll('a, li').length > 0
                            );
                            
                            for (const el of hotElements) {
                                const items = Array.from(el.querySelectorAll('a, li'))
                                    .filter(item => item.textContent.trim().length > 0)
                                    .map(item => item.textContent.trim())
                                    .filter(text => text.length > 1 && !text.includes('热搜'));
                                
                                if (items.length > 0) {
                                    hotItems = [...hotItems, ...items];
                                }
                            }
                            
                            // 淘宝特定处理
                            const taobaoHotSearches = Array.from(document.querySelectorAll('.search-hots-lines li, .search-hots-fline li, .hot-word a, .hot-query a')).map(el => el.textContent.trim());
                            if (taobaoHotSearches.length > 0) {
                                hotItems = [...hotItems, ...taobaoHotSearches];
                            }
                            
                            // 返回所有找到的热搜项目
                            return Array.from(new Set(hotItems)).slice(0, 20); // 去重并限制数量
                        })();
                        """
                    }
                }))
                
                hot_response = await ws.recv()
                hot_data = json.loads(hot_response)
                
                if hot_data.get('result', {}).get('result', {}).get('type') == 'object':
                    # print("热搜信息需要进一步处理，尝试另一种方法...")
                    
                    # 尝试另一种方法获取热搜
                    await ws.send(json.dumps({
                        "id": 401,
                        "method": "Runtime.evaluate",
                        "params": {
                            "expression": """
                            (function() {
                                // 更简单的方法：直接查找所有可能是热搜的元素
                                let results = [];
                                const searchKeywords = [
                                    // 通用类名
                                    '.hot-search', '.trending', '.popular-searches', 
                                    // 淘宝特定类名
                                    '.search-hots-lines', '.search-hots-fline', '.hot-word', '.hot-query',
                                    // 其他常见类名
                                    '.trend-list', '.hot-list', '.trending-now'
                                ];
                                
                                for (const selector of searchKeywords) {
                                    try {
                                        const elements = document.querySelectorAll(selector);
                                        for (const el of elements) {
                                            results.push(el.innerText);
                                        }
                                    } catch (e) {}
                                }
                                
                                if (results.length === 0) {
                                    // 最后尝试：所有短文本链接
                                    const shortLinks = Array.from(document.querySelectorAll('a')).filter(a => {
                                        const text = a.textContent.trim();
                                        return text.length > 1 && text.length < 20 && !a.querySelector('img');
                                    }).map(a => a.textContent.trim());
                                    
                                    // 仅当数量合理时才添加
                                    if (shortLinks.length > 0 && shortLinks.length < 30) {
                                        results.push('可能的热搜链接: ' + shortLinks.join(' | '));
                                    }
                                }
                                
                                return results.join('\n\n');
                            })();
                            """
                        }
                    }))
                    
                    hot_text_response = await ws.recv()
                    hot_text_data = json.loads(hot_text_response)
                    hot_search_text = hot_text_data.get('result', {}).get('result', {}).get('value', '未找到热搜信息')
                    
                #     print("\n可能的热搜信息:")
                #     print("-" * 50)
                #     print(hot_search_text)
                #     print("-" * 50)
                # else:
                #     hot_searches = hot_data.get('result', {}).get('result', {}).get('value', [])
                    
                    # print("\n找到的热搜信息:")
                    # print("-" * 50)
                    # for i, item in enumerate(hot_searches):
                    #     print(f"{i+1}. {item}")
                    # print("-" * 50)
                
            except Exception as e:
                print(f"获取HTML时出错: {e}")
                import traceback
                traceback.print_exc()
                
    except websockets.exceptions.ConnectionClosed as e:
        print(f"WebSocket连接关闭: {e}")
    except ConnectionRefusedError:
        print("连接被拒绝。请确保Chrome浏览器正在以远程调试模式运行。")
        print("启动Chrome的命令示例: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --remote-debugging-port=9222'")
    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()

# 主程序
if __name__ == "__main__":
    print("开始运行Chrome页面内容捕获脚本...")
    asyncio.run(capture_content())
    print("\n脚本执行完成。")
    
    print("\n提示: 如果您想获取Chrome调试页面的列表，可以运行:")
    print("curl http://localhost:9222/json")
    print("\n如果需要启动Chrome浏览器的调试模式，可以运行:")
    print("'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' --remote-debugging-port=9222")