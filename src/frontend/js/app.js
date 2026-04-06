// 全局调试日志数组
window.debugLogs = [];

// 调试日志函数
function debugLog(message, data) {
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = `[${timestamp}] ${message} ${data ? JSON.stringify(data) : ''}`;
    console.log(logEntry);
    window.debugLogs.push(logEntry);
    if (window.debugLogs.length > 100) {
        window.debugLogs.shift();
    }
}

// 全局错误处理
window.onerror = function(msg, url, line, col, error) {
    const errorMsg = `JS错误: ${msg} 行:${line}`;
    debugLog(errorMsg);
    alert(errorMsg);
    return false;
};

function downloadApp() {
    debugLog('downloadApp() 开始执行');
    
    try {
            // 基础数据对象
        const app = {
            // 状态
            tasks: [],
            // 确保 tasks 始终有默认值
            _tasks: [],
            stats: {
                download_speed: 0,
                upload_speed: 0,
                num_active: 0,
                num_waiting: 0,
                num_stopped: 0
            },
            config: {
                default_download_dir: '',
                default_connections: 16,
                default_splits: 16,
                max_concurrent_downloads: 5
            },
            filter: 'all',
            darkMode: false,
            showNewTask: false,
            showSettings: false,
            showDebug: false,
            debugLogs: window.debugLogs,
            toast: {
                message: '',
                type: 'success'
            },
            
            // 新任务表单
            newTask: {
                urls: '',
                save_dir: '',
                filename: '',
                connections: 16,
                splits: 16,
                max_speed: ''
            },
            
            // 创建任务状态
            creatingTask: false,
            
            // 初始化
            init() {
                debugLog('init() 开始');
                
                // 延迟检查 pywebview 是否可用（给 pywebview 初始化时间）
                setTimeout(() => {
                    this.checkPywebview();
                }, 500);
                
                try {
                    // 安全地读取 localStorage
                    try {
                        this.darkMode = localStorage.getItem('darkMode') === 'true';
                    } catch (e) {
                        debugLog('localStorage 读取失败: ' + e);
                    }
                    
                    this.updateTheme();
                    this.loadConfig();
                    this.refreshData();
                    // 增加刷新间隔到 2 秒，减少 RPC 负担
                    setInterval(() => this.refreshData(), 2000);
                    debugLog('init() 完成');
                } catch (e) {
                    debugLog('init() 出错: ' + e);
                }
            },
            
            // 检查 pywebview 可用性
            checkPywebview() {
                debugLog('检查 pywebview...');
                if (window.pywebview) {
                    debugLog('pywebview 对象存在');
                    if (window.pywebview.api) {
                        debugLog('pywebview.api 存在，方法: ' + Object.keys(window.pywebview.api).join(', '));
                    } else {
                        debugLog('pywebview.api 不存在!');
                    }
                } else {
                    debugLog('pywebview 对象不存在 - 在浏览器中运行');
                }
            },
            
            // 刷新数据
            async refreshData() {
                try {
                    const tasksResponse = await fetch('/api/tasks');
                    if (tasksResponse.ok) {
                        const data = await tasksResponse.json();
                        // 确保数据是数组
                        this.tasks = Array.isArray(data) ? data : [];
                        this._tasks = this.tasks;
                    } else {
                        // 如果请求失败，保持原有数据
                        this.tasks = this._tasks;
                    }
                    
                    const statsResponse = await fetch('/api/stats');
                    if (statsResponse.ok) {
                        this.stats = await statsResponse.json();
                    }
                } catch (error) {
                    // 静默处理
                }
            },
            
            // 加载配置
            async loadConfig() {
                try {
                    const response = await fetch('/api/config');
                    if (response.ok) {
                        const config = await response.json();
                        this.config = config;
                        this.newTask.connections = config.default_connections || 16;
                        this.newTask.splits = config.default_splits || 16;
                        this.newTask.save_dir = config.default_download_dir || '';
                        debugLog('配置加载成功');
                    }
                } catch (error) {
                    debugLog('配置加载失败: ' + error);
                }
            },
            
            // 保存配置
            async saveConfig() {
                debugLog('saveConfig()');
                try {
                    const response = await fetch('/api/config', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(this.config)
                    });
                    
                    if (response.ok) {
                        this.showToast('配置已保存');
                        this.showSettings = false;
                    } else {
                        this.showToast('保存配置失败', 'error');
                    }
                } catch (error) {
                    this.showToast('保存配置失败', 'error');
                }
            },
            
            // 创建任务
            async createTask() {
                debugLog('createTask()');
                
                // 防止重复提交
                if (this.creatingTask) {
                    debugLog('任务创建中，忽略重复点击');
                    return;
                }
                
                const urls = this.newTask.urls.trim().split('\n').filter(u => u.trim());
                if (urls.length === 0) {
                    this.showToast('请输入下载链接', 'error');
                    return;
                }
                
                this.creatingTask = true;
                debugLog('开始创建任务，URLs: ' + urls.length + ' 个');
                
                try {
                    // 显示加载状态
                    this.showToast('正在创建任务...', 'success');
                    
                    // 立即关闭弹窗，提供流畅体验
                    this.showNewTask = false;
                    const savedNewTask = { ...this.newTask };
                    this.resetNewTask();

                    const response = await fetch('/api/tasks', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            ...savedNewTask,
                            urls: urls
                        })
                    });
                    
                    debugLog('创建任务响应: ' + response.status);
                    
                    if (response.ok) {
                        const result = await response.json();
                        debugLog('任务创建成功: ' + JSON.stringify(result));
                        this.showToast('任务创建成功');
                        await this.refreshData();
                    } else {
                        // 如果失败，重新打开弹窗或显示错误
                        this.showNewTask = true;
                        this.newTask = savedNewTask;
                        const error = await response.json();
                        debugLog('创建任务失败: ' + JSON.stringify(error));
                        this.showToast(error.detail || '创建任务失败', 'error');
                    }
                } catch (error) {
                    debugLog('创建任务异常: ' + error);
                    this.showToast('创建任务失败: ' + error.message, 'error');
                } finally {
                    this.creatingTask = false;
                }
            },
            
            // 重置新任务表单
            resetNewTask() {
                this.newTask = {
                    urls: '',
                    save_dir: this.config.default_download_dir || '',
                    filename: '',
                    connections: this.config.default_connections || 16,
                    splits: this.config.default_splits || 16,
                    max_speed: ''
                };
            },
            
            // 暂停任务
            async pauseTask(gid) {
                debugLog('pauseTask(' + gid + ')');
                try {
                    const response = await fetch(`/api/tasks/${gid}/pause`, {
                        method: 'POST'
                    });
                    debugLog('pauseTask 响应: ' + response.status);
                    if (response.ok) {
                        this.showToast('任务已暂停');
                        await this.refreshData();
                    } else {
                        const error = await response.json();
                        this.showToast(error.detail || '暂停任务失败', 'error');
                    }
                } catch (error) {
                    debugLog('pauseTask 错误: ' + error);
                    this.showToast('暂停任务失败', 'error');
                }
            },
            
            // 继续任务
            async resumeTask(gid) {
                debugLog('resumeTask(' + gid + ')');
                try {
                    const response = await fetch(`/api/tasks/${gid}/resume`, {
                        method: 'POST'
                    });
                    debugLog('resumeTask 响应: ' + response.status);
                    if (response.ok) {
                        this.showToast('任务已继续');
                        await this.refreshData();
                    } else {
                        const error = await response.json();
                        this.showToast(error.detail || '继续任务失败', 'error');
                    }
                } catch (error) {
                    debugLog('resumeTask 错误: ' + error);
                    this.showToast('继续任务失败', 'error');
                }
            },
            
            // 删除任务
            async removeTask(gid) {
                debugLog('removeTask(' + gid + ')');
                if (!confirm('确定要删除这个任务吗？')) {
                    return;
                }
                
                try {
                    const response = await fetch(`/api/tasks/${gid}`, {
                        method: 'DELETE'
                    });
                    debugLog('removeTask 响应: ' + response.status);
                    if (response.ok) {
                        this.showToast('任务已删除');
                        await this.refreshData();
                    } else {
                        const error = await response.json();
                        this.showToast(error.detail || '删除任务失败', 'error');
                    }
                } catch (error) {
                    debugLog('removeTask 错误: ' + error);
                    this.showToast('删除任务失败', 'error');
                }
            },
            
            // 暂停所有任务
            async pauseAll() {
                debugLog('pauseAll()');
                try {
                    const response = await fetch('/api/tasks/pause-all', {
                        method: 'POST'
                    });
                    debugLog('pauseAll 响应: ' + response.status);
                    if (response.ok) {
                        this.showToast('所有任务已暂停');
                        await this.refreshData();
                    } else {
                        const error = await response.json();
                        this.showToast(error.detail || '操作失败', 'error');
                    }
                } catch (error) {
                    debugLog('pauseAll 错误: ' + error);
                    this.showToast('操作失败', 'error');
                }
            },
            
            // 继续所有任务
            async resumeAll() {
                debugLog('resumeAll()');
                try {
                    const response = await fetch('/api/tasks/resume-all', {
                        method: 'POST'
                    });
                    debugLog('resumeAll 响应: ' + response.status);
                    if (response.ok) {
                        this.showToast('所有任务已继续');
                        await this.refreshData();
                    } else {
                        const error = await response.json();
                        this.showToast(error.detail || '操作失败', 'error');
                    }
                } catch (error) {
                    debugLog('resumeAll 错误: ' + error);
                    this.showToast('操作失败', 'error');
                }
            },
            
            // 选择目录
            async selectDirectory() {
                debugLog('selectDirectory()');
                try {
                    // 检查是否在 pywebview 环境中
                    if (window.pywebview && window.pywebview.api) {
                        debugLog('使用 pywebview.api.select_save_directory()');
                        const dir = await window.pywebview.api.select_save_directory();
                        debugLog('选择的目录: ' + dir);
                        if (dir) {
                            this.newTask.save_dir = dir;
                        }
                    } else {
                        // 回退到 prompt
                        debugLog('使用 prompt 回退');
                        const dir = prompt('请输入下载目录:', this.newTask.save_dir);
                        if (dir) {
                            this.newTask.save_dir = dir;
                        }
                    }
                } catch (error) {
                    debugLog('selectDirectory 错误: ' + error);
                    // 出错时回退到 prompt
                    const dir = prompt('请输入下载目录:', this.newTask.save_dir);
                    if (dir) {
                        this.newTask.save_dir = dir;
                    }
                }
            },
            
            // 选择默认目录
            async selectDefaultDirectory() {
                debugLog('selectDefaultDirectory()');
                try {
                    // 检查是否在 pywebview 环境中
                    if (window.pywebview && window.pywebview.api) {
                        debugLog('使用 pywebview.api.select_default_directory()');
                        const dir = await window.pywebview.api.select_default_directory();
                        debugLog('选择的目录: ' + dir);
                        if (dir) {
                            this.config.default_download_dir = dir;
                        }
                    } else {
                        // 回退到 prompt
                        debugLog('使用 prompt 回退');
                        const dir = prompt('请输入默认下载目录:', this.config.default_download_dir);
                        if (dir) {
                            this.config.default_download_dir = dir;
                        }
                    }
                } catch (error) {
                    debugLog('selectDefaultDirectory 错误: ' + error);
                    // 出错时回退到 prompt
                    const dir = prompt('请输入默认下载目录:', this.config.default_download_dir);
                    if (dir) {
                        this.config.default_download_dir = dir;
                    }
                }
            },
            
            // 切换主题
            toggleTheme() {
                this.darkMode = !this.darkMode;
                try {
                    localStorage.setItem('darkMode', this.darkMode);
                } catch (e) {
                    debugLog('localStorage 保存失败: ' + e);
                }
                this.updateTheme();
            },
            
            // 更新主题
            updateTheme() {
                if (this.darkMode) {
                    document.documentElement.classList.add('dark');
                } else {
                    document.documentElement.classList.remove('dark');
                }
            },
            
            // 显示提示
            showToast(message, type = 'success') {
                this.toast.message = message;
                this.toast.type = type;
                setTimeout(() => {
                    this.toast.message = '';
                }, 3000);
            },
            
            // 获取状态样式
            getStatusClass(status) {
                const classes = {
                    'active': 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
                    'waiting': 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
                    'paused': 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300',
                    'error': 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
                    'complete': 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
                    'removed': 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                };
                return classes[status] || classes['waiting'];
            },
            
            // 获取状态文本
            getStatusText(status) {
                const texts = {
                    'active': '下载中',
                    'waiting': '等待中',
                    'paused': '已暂停',
                    'error': '出错',
                    'complete': '已完成',
                    'removed': '已删除'
                };
                return texts[status] || status;
            },
            
            // 格式化文件大小
            formatSize(bytes) {
                if (!bytes || bytes === 0) return '0 B';
                const k = 1024;
                const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
            },
            
            // 格式化速度
            formatSpeed(bytesPerSecond) {
                return this.formatSize(bytesPerSecond) + '/s';
            },
            
            // 过滤后的任务列表
            get filteredTasks() {
                // 确保 tasks 是数组，避免 undefined 错误
                if (!Array.isArray(this.tasks)) {
                    return [];
                }
                if (this.filter === 'all') {
                    return this.tasks;
                }
                return this.tasks.filter(task => task.status === this.filter);
            }
        };
        
        debugLog('downloadApp() 返回对象成功');
        return app;
        
    } catch (error) {
        debugLog('downloadApp() 执行出错: ' + error);
        alert('App 初始化失败: ' + error);
        
        // 返回一个最小化的对象，避免完全崩溃
        return {
            showNewTask: false,
            showSettings: false,
            showDebug: false,
            debugLogs: window.debugLogs,
            init() {
                debugLog('使用备用 init');
            }
        };
    }
}

debugLog('app.js 加载完成');
