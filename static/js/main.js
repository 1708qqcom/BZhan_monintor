/**
 * B站UP主监控系统 - 前端交互脚本
 *
 * 功能：
 * - 导航栏交互
 * - API 请求封装
 * - 全局状态管理
 * - 工具函数
 */

// ==================== 全局状态管理 ====================

const AppState = {
    // 当前页面
    currentPage: '',

    // 用户信息
    user: null,

    // 缓存数据
    cache: new Map(),
};

// ==================== 工具函数 ====================

/**
 * HTML 转义
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * 格式化日期时间
 */
function formatDateTime(isoString) {
    if (!isoString) return '-';

    try {
        const date = new Date(isoString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        // 1小时内显示"刚刚"
        if (diffMins < 1) return '刚刚';
        if (diffMins < 60) return `${diffMins}分钟前`;

        // 24小时内显示小时
        if (diffHours < 24) return `${diffHours}小时前`;

        // 7天内显示天数
        if (diffDays < 7) return `${diffDays}天前`;

        // 超过7天显示日期
        return date.toLocaleDateString('zh-CN');
    } catch (e) {
        console.error('[formatDateTime] 格式化失败:', e);
        return isoString;
    }
}

/**
 * 显示全局错误提示
 *
 * 显示时移除 hidden 与 translate-x-full 使其滑入；
 * duration 后滑出，动画结束再 hidden，避免提示常驻屏幕外。
 *
 * @param {string} message - 错误信息（支持HTML）
 * @param {number} duration - 显示时长（毫秒），默认5000ms
 */
function showError(message, duration = 5000) {
    console.error('[Global Error]', message);

    const container = document.getElementById('global-error');
    const messageEl = document.getElementById('global-error-message');

    if (!container || !messageEl) {
        console.warn('[Global Error] 提示容器不存在，跳过显示');
        return;
    }

    // 支持HTML内容（用于显示跳转链接）
    messageEl.innerHTML = message;

    // 清除前一个隐藏定时器，避免连续触发时提前隐藏
    if (container._hideTimer) {
        clearTimeout(container._hideTimer);
    }

    // 显示并滑入
    container.classList.remove('hidden', 'translate-x-full');

    // 延后滑出并隐藏
    container._hideTimer = setTimeout(() => {
        container.classList.add('translate-x-full');
        setTimeout(() => container.classList.add('hidden'), 300);
    }, duration);
}

/**
 * 显示全局成功提示
 *
 * 显示时移除 hidden 与 translate-x-full 使其滑入；
 * duration 后滑出，动画结束再 hidden。
 */
function showSuccess(message, duration = 3000) {
    console.log('[Global Success]', message);

    const container = document.getElementById('global-success');
    const messageEl = document.getElementById('global-success-message');

    if (!container || !messageEl) {
        console.warn('[Global Success] 提示容器不存在，跳过显示');
        return;
    }

    messageEl.textContent = message;

    // 清除前一个隐藏定时器，避免连续触发时提前隐藏
    if (container._hideTimer) {
        clearTimeout(container._hideTimer);
    }

    // 显示并滑入
    container.classList.remove('hidden', 'translate-x-full');

    // 延后滑出并隐藏
    container._hideTimer = setTimeout(() => {
        container.classList.add('translate-x-full');
        setTimeout(() => container.classList.add('hidden'), 300);
    }, duration);
}

/**
 * 封装 fetch 请求
 *
 * @param {string} url - 请求 URL
 * @param {object} options - fetch 选项
 * @returns {Promise<any>} - 响应数据
 */
async function fetchAPI(url, options = {}) {
    console.log('[fetchAPI] 请求:', url);

    try {
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
        });

        // 检查响应状态
        if (!response.ok) {
            const error = await response.json().catch(() => ({
                error: 'Request failed',
                detail: `HTTP ${response.status}`
            }));

            // 401 未认证
            if (response.status === 401) {
                console.warn('[fetchAPI] 未认证，跳转登录页');
                window.location.href = '/auth/login';
                throw new Error('请先登录');
            }

            throw new Error(error.detail || error.error || '请求失败');
        }

        const data = await response.json();
        console.log('[fetchAPI] 响应:', url, data);

        return data;

    } catch (error) {
        console.error('[fetchAPI] 错误:', url, error);
        throw error;
    }
}

/**
 * 显示 Loading 状态
 */
function showLoading(elementId) {
    const el = document.getElementById(elementId);
    if (el) {
        el.innerHTML = `
            <div class="text-center py-8 text-gray-500">
                <svg class="animate-spin w-6 h-6 mx-auto mb-2" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 2.042.784 3.87 2.058 5.244L6 17.291z"></path>
                </svg>
                <p>加载中...</p>
            </div>
        `;
    }
}

// ==================== 导航栏交互 ====================

/**
 * 切换移动端菜单显隐（带滑入/滑出动画）
 *
 * 菜单初始同时带 -translate-y-full（上移到视口外）与 hidden（display:none）。
 * 打开时先解除 hidden，强制重排后再解除位移类，触发滑入；
 * 关闭时先加回位移类滑出，动画结束后再 hidden，避免菜单常驻视口外。
 *
 * @param {HTMLElement} menu - 移动端菜单容器 (#mobile-menu)
 * @param {boolean} willOpen - true 打开，false 关闭
 */
function toggleMobileMenu(menu, willOpen) {
    if (willOpen) {
        menu.classList.remove('hidden');
        // 强制重排，确保后续 transform 变化能触发 transition
        void menu.offsetHeight;
        menu.classList.remove('-translate-y-full');
        menu.classList.add('translate-y-0');
    } else {
        menu.classList.remove('translate-y-0');
        menu.classList.add('-translate-y-full');
        // 等待滑出动画（duration-300）结束后再 display:none
        setTimeout(() => menu.classList.add('hidden'), 300);
    }
}

/**
 * 初始化移动端汉堡菜单交互
 *
 * 职责：绑定按钮开/关 + 菜单项点击后关闭。
 * 元素缺失时降级为告警日志，不抛异常，避免阻塞其余导航初始化。
 */
function initMobileMenu() {
    const menuButton = document.getElementById('mobile-menu-button');
    const mobileMenu = document.getElementById('mobile-menu');

    if (!menuButton || !mobileMenu) {
        console.warn('[Nav] 移动端菜单元素缺失，跳过初始化');
        return;
    }

    menuButton.addEventListener('click', function () {
        const willOpen = mobileMenu.classList.contains('hidden');
        console.log('[Nav] 切换移动端菜单，willOpen =', willOpen);
        toggleMobileMenu(mobileMenu, willOpen);
    });

    // 点击菜单内任一链接/按钮后关闭菜单（跳转或提交前复位视图）
    mobileMenu.querySelectorAll('a, button').forEach(function (item) {
        item.addEventListener('click', function () {
            toggleMobileMenu(mobileMenu, false);
        });
    });
}

/**
 * 高亮当前页面对应的导航链接
 */
function markCurrentNav() {
    const currentPath = window.location.pathname;
    document.querySelectorAll('nav a').forEach(function (link) {
        if (link.getAttribute('href') === currentPath) {
            link.classList.remove('text-gray-500');
            link.classList.add('text-gray-900');
        }
    });
}

document.addEventListener('DOMContentLoaded', function () {
    console.log('[Main] 页面加载完成，初始化导航栏');
    initMobileMenu();
    markCurrentNav();
    console.log('[Main] 导航栏初始化完成');
});

// ==================== 导出函数 ====================

window.AppState = AppState;
window.escapeHtml = escapeHtml;
window.formatDateTime = formatDateTime;
window.showError = showError;
window.showSuccess = showSuccess;
window.fetchAPI = fetchAPI;
window.showLoading = showLoading;