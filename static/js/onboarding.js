/**
 * 用户引导流程交互脚本
 *
 * 功能：
 * - 3步引导流程控制
 * - B站扫码登录
 * - 飞书 Webhook 配置
 * - UP主批量选择
 * - 进度跟踪和步骤切换
 */
(function () {
    'use strict';

    // ==================== 状态管理 ====================
    const OnboardingState = {
        currentStep: 1,        // 当前步骤
        progress: null,        // 引导进度
        selectedUps: [],       // 选中的UP主ID
        upsList: [],           // UP主列表
        bilibiliBound: false,  // B站是否已绑定
        pollTimer: null        // B站扫码轮询定时器
    };

    // DOM 缓存
    const Dom = {};

    function cacheDom() {
        Dom.stepContents = {
            1: document.getElementById('step1-content'),
            2: document.getElementById('step2-content'),
            3: document.getElementById('step3-content')
        };
        Dom.indicators = {
            1: document.getElementById('step1-indicator'),
            2: document.getElementById('step2-indicator'),
            3: document.getElementById('step3-indicator')
        };
        Dom.lines = {
            1: document.getElementById('line1'),
            2: document.getElementById('line2')
        };
        Dom.btnPrev = document.getElementById('btn-prev');
        Dom.btnNext = document.getElementById('btn-next');
        Dom.btnSkip = document.getElementById('btn-skip');
        Dom.btnComplete = document.getElementById('btn-complete');
        Dom.progressPercent = document.getElementById('progress-percent');
    }

    // ==================== 初始化 ====================
    async function init() {
        cacheDom();
        await loadOnboardingProgress();
        setupEventListeners();
    }

    // ==================== 进度管理 ====================
    async function loadOnboardingProgress() {
        try {
            const response = await fetchAPI('/api/onboarding/status');
            if (response.has_onboarding_record && response.progress) {
                OnboardingState.progress = response.progress;

                const progress = response.progress;

                // 如果已完成，直接跳转仪表盘
                if (progress.is_completed) {
                    window.location.href = '/';
                    return;
                }

                OnboardingState.currentStep = progress.current_step;

                // 检查B站绑定状态
                await checkBilibiliBinding();
            }

            switchToStep(OnboardingState.currentStep);
        } catch (error) {
            console.error('[Onboarding] 加载进度失败:', error);
            switchToStep(1);
        }
    }

    async function updateProgress() {
        try {
            const response = await fetchAPI('/api/onboarding/status');
            if (response.has_onboarding_record && response.progress) {
                OnboardingState.progress = response.progress;
                updateProgressUI();
            }
        } catch (error) {
            console.error('[Onboarding] 更新进度失败:', error);
        }
    }

    function updateProgressUI() {
        const progress = OnboardingState.progress;
        if (!progress) return;

        // 更新百分比
        Dom.progressPercent.textContent = progress.progress_percent + '%';

        // 更新步骤指示器
        const steps = [1, 2, 3];
        steps.forEach(function (step) {
            const indicator = Dom.indicators[step];
            if (!indicator) return;

            const isCompleted = progress['step' + step + '_completed'];
            const isSkipped = progress['step' + step + '_skipped'];

            if (isCompleted || isSkipped) {
                // 已完成或已跳过
                indicator.className = 'w-10 h-10 rounded-full flex items-center justify-center border-2 bg-green-100 border-green-300 text-green-600 font-medium';
                indicator.innerHTML = isSkipped ? '⏭' : '<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>';
            } else if (step === OnboardingState.currentStep) {
                // 当前步骤
                indicator.className = 'w-10 h-10 rounded-full flex items-center justify-center border-2 bg-primary border-primary text-white font-medium';
                indicator.textContent = step;
            } else {
                // 未完成
                indicator.className = 'w-10 h-10 rounded-full flex items-center justify-center border-2 bg-gray-200 border-gray-300 text-gray-500 font-medium';
                indicator.textContent = step;
            }
        });

        // 更新连接线
        if (Dom.lines[1]) {
            Dom.lines[1].style.width = (progress.step1_completed || progress.step1_skipped) ? '100%' : '0%';
        }
        if (Dom.lines[2]) {
            Dom.lines[2].style.width = (progress.step2_completed || progress.step2_skipped) ? '100%' : '0%';
        }
    }

    // ==================== 步骤切换 ====================
    function switchToStep(step) {
        OnboardingState.currentStep = step;

        // 显示/隐藏步骤内容
        Object.keys(Dom.stepContents).forEach(function (key) {
            if (Dom.stepContents[key]) {
                Dom.stepContents[key].classList.add('hidden');
            }
        });

        if (Dom.stepContents[step]) {
            Dom.stepContents[step].classList.remove('hidden');
        }

        // 更新按钮状态
        updateButtons(step);

        // 更新进度UI
        updateProgressUI();

        // 加载步骤特定内容
        loadStepContent(step);
    }

    function updateButtons(step) {
        // 上一步按钮
        Dom.btnPrev.classList.toggle('hidden', step === 1);

        // 下一步/完成按钮
        if (step === 3) {
            Dom.btnNext.classList.add('hidden');
            Dom.btnComplete.classList.remove('hidden');
        } else {
            Dom.btnNext.classList.remove('hidden');
            Dom.btnComplete.classList.add('hidden');
        }
    }

    function loadStepContent(step) {
        switch (step) {
            case 1: loadStep1Content(); break;
            case 2: loadStep2Content(); break;
            case 3: loadStep3Content(); break;
        }
    }

    // ==================== 步骤 1：B站登录 ====================
    async function loadStep1Content() {
        try {
            await checkBilibiliBinding();
            if (OnboardingState.bilibiliBound) {
                // 已绑定，显示成功状态
                document.getElementById('qrcode-image').innerHTML = `
                    <div class="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto">
                        <svg class="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                        </svg>
                    </div>
                `;
                document.getElementById('qrcode-status').textContent = 'B站账号已绑定';
                document.getElementById('btn-get-qrcode').textContent = '重新获取二维码';
            }
        } catch (error) {
            console.error('[Onboarding] 检查B站绑定状态失败:', error);
        }
    }

    async function checkBilibiliBinding() {
        try {
            const response = await fetchAPI('/api/login/binding-status');
            OnboardingState.bilibiliBound = response.data && response.data.is_bound;
        } catch (error) {
            OnboardingState.bilibiliBound = false;
        }
    }

    async function getQrcode() {
        try {
            const qrcode = await fetchAPI('/api/login/qrcode');
            document.getElementById('qrcode-image').innerHTML =
                '<img src="' + qrcode.image_url + '" alt="B站登录二维码" class="w-48 h-48">';
            document.getElementById('qrcode-status').textContent = '请使用B站App扫描二维码登录';
            startQrcodePolling();
        } catch (error) {
            document.getElementById('qrcode-status').textContent = '获取二维码失败，请重试';
            console.error('[Onboarding] 获取二维码失败:', error);
        }
    }

    function startQrcodePolling() {
        stopQrcodePolling();

        OnboardingState.pollTimer = setInterval(async function () {
            try {
                const result = await fetchAPI('/api/login/poll', { method: 'POST' });
                if (result.data && result.data.status === 'success') {
                    stopQrcodePolling();
                    document.getElementById('qrcode-status').textContent = '✓ 登录成功！';
                    OnboardingState.bilibiliBound = true;
                    showSuccess('B站账号绑定成功');
                    // 自动进入下一步
                    await completeOnboardingStep(1);
                    switchToStep(2);
                } else if (result.data && result.data.status === 'expired') {
                    stopQrcodePolling();
                    document.getElementById('qrcode-status').textContent = '二维码已过期，请重新获取';
                }
            } catch (error) {
                console.error('[Onboarding] 轮询失败:', error);
            }
        }, 2000);

        // 3分钟后自动停止
        setTimeout(stopQrcodePolling, 180000);
    }

    function stopQrcodePolling() {
        if (OnboardingState.pollTimer) {
            clearInterval(OnboardingState.pollTimer);
            OnboardingState.pollTimer = null;
        }
    }

    // ==================== 步骤 2：飞书配置 ====================
    async function loadStep2Content() {
        try {
            const config = await fetchAPI('/api/config');
            const input = document.getElementById('feishu-webhook');
            if (input && config.feishu_webhook_url) {
                input.value = config.feishu_webhook_url;
            }
        } catch (error) {
            console.error('[Onboarding] 加载飞书配置失败:', error);
        }
    }

    async function saveFeishuConfig() {
        const webhookUrl = document.getElementById('feishu-webhook').value.trim();
        if (!webhookUrl) {
            showError('请输入飞书 Webhook URL');
            return false;
        }

        try {
            await fetchAPI('/api/config', {
                method: 'PUT',
                body: JSON.stringify({ feishu_webhook_url: webhookUrl })
            });
            showSuccess('飞书配置保存成功');
            return true;
        } catch (error) {
            showError('配置保存失败: ' + error.message);
            return false;
        }
    }

    async function testFeishuPush() {
        const statusEl = document.getElementById('test-push-status');
        statusEl.textContent = '正在发送测试消息...';

        try {
            await fetchAPI('/api/config/test-push', {
                method: 'POST',
                body: JSON.stringify({ message: '引导流程测试消息' })
            });
            statusEl.textContent = '✓ 测试推送成功';
            statusEl.className = 'text-xs text-center mt-2 text-green-600';
        } catch (error) {
            statusEl.textContent = '✗ 测试推送失败: ' + error.message;
            statusEl.className = 'text-xs text-center mt-2 text-red-600';
        }
    }

    // ==================== 步骤 3：UP主选择 ====================
    async function loadStep3Content() {
        if (!OnboardingState.bilibiliBound) {
            document.getElementById('ups-container').innerHTML = `
                <div class="text-center py-8">
                    <p class="text-sm text-gray-500">请先完成步骤1：绑定B站账号</p>
                </div>
            `;
            return;
        }

        try {
            const response = await fetchAPI('/api/ups?page=1&page_size=100');
            OnboardingState.upsList = response.items || [];
            renderUpsList(OnboardingState.upsList);
        } catch (error) {
            console.error('[Onboarding] 加载UP主列表失败:', error);
            document.getElementById('ups-container').innerHTML = `
                <div class="text-center py-8 text-red-500">
                    加载UP主列表失败: ${escapeHtml(error.message)}
                </div>
            `;
        }
    }

    function renderUpsList(upsList) {
        const container = document.getElementById('ups-container');

        if (upsList.length === 0) {
            container.innerHTML = `
                <div class="text-center py-12 text-gray-500">
                    <p class="text-sm">暂无UP主数据</p>
                    <p class="text-xs mt-1">请先在步骤1中同步B站关注列表</p>
                </div>
            `;
            return;
        }

        // 默认全选
        OnboardingState.selectedUps = upsList.map(function (up) { return up.id; });

        container.innerHTML = upsList.map(function (up) {
            return `
                <div class="flex items-center p-3 border-b border-gray-100 hover:bg-gray-50 transition-colors">
                    <input type="checkbox" class="ups-checkbox w-4 h-4 text-primary rounded border-gray-300 focus:ring-primary"
                           data-up-id="${up.id}" checked>
                    <img src="${up.face || ''}" alt="${escapeHtml(up.name)}" class="w-8 h-8 rounded-full mx-3"
                         onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22><path fill=%22%23ccc%22 d=%22M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zM12 14c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z%22/></svg>'">
                    <span class="text-sm font-medium text-gray-900">${escapeHtml(up.name)}</span>
                </div>
            `;
        }).join('');

        // 绑定复选框事件
        container.querySelectorAll('.ups-checkbox').forEach(function (checkbox) {
            checkbox.addEventListener('change', function () {
                var upId = parseInt(this.dataset.upId);
                if (this.checked) {
                    if (OnboardingState.selectedUps.indexOf(upId) === -1) {
                        OnboardingState.selectedUps.push(upId);
                    }
                } else {
                    OnboardingState.selectedUps = OnboardingState.selectedUps.filter(function (id) {
                        return id !== upId;
                    });
                }
            });
        });
    }

    function selectAllUps() {
        OnboardingState.selectedUps = OnboardingState.upsList.map(function (up) { return up.id; });
        document.querySelectorAll('.ups-checkbox').forEach(function (checkbox) {
            checkbox.checked = true;
        });
    }

    function selectNoneUps() {
        OnboardingState.selectedUps = [];
        document.querySelectorAll('.ups-checkbox').forEach(function (checkbox) {
            checkbox.checked = false;
        });
    }

    // ==================== 步骤完成/跳过 ====================
    async function completeOnboardingStep(step) {
        try {
            await fetchAPI('/api/onboarding/complete-step', {
                method: 'POST',
                body: JSON.stringify({ step: step })
            });
            await updateProgress();
            console.log('[Onboarding] 步骤 ' + step + ' 已完成');
        } catch (error) {
            console.error('[Onboarding] 完成步骤失败:', error);
            throw error;
        }
    }

    async function skipOnboardingStep(step) {
        try {
            await fetchAPI('/api/onboarding/skip-step', {
                method: 'POST',
                body: JSON.stringify({ step: step })
            });
            await updateProgress();
            showSuccess('步骤 ' + step + ' 已跳过');
            console.log('[Onboarding] 步骤 ' + step + ' 已跳过');
        } catch (error) {
            console.error('[Onboarding] 跳过步骤失败:', error);
            throw error;
        }
    }

    // ==================== 事件处理 ====================
    function setupEventListeners() {
        // 步骤 1 事件
        document.getElementById('btn-get-qrcode').addEventListener('click', function () {
            getQrcode();
        });

        // 步骤 2 事件
        document.getElementById('btn-test-push').addEventListener('click', function () {
            testFeishuPush();
        });

        // 步骤 3 事件
        document.getElementById('btn-select-all').addEventListener('click', selectAllUps);
        document.getElementById('btn-select-none').addEventListener('click', selectNoneUps);

        // 导航按钮
        Dom.btnPrev.addEventListener('click', function () {
            switchToStep(OnboardingState.currentStep - 1);
        });

        Dom.btnNext.addEventListener('click', async function () {
            var currentStep = OnboardingState.currentStep;

            // 步骤 2 需要保存飞书配置
            if (currentStep === 2) {
                var saved = await saveFeishuConfig();
                if (!saved) return;
            }

            try {
                await completeOnboardingStep(currentStep);
                switchToStep(currentStep + 1);
            } catch (error) {
                showError('操作失败: ' + error.message);
            }
        });

        Dom.btnComplete.addEventListener('click', async function () {
            try {
                await completeOnboardingStep(3);
                showSuccess('配置完成！正在跳转到仪表盘...');
                setTimeout(function () {
                    window.location.href = '/';
                }, 1500);
            } catch (error) {
                showError('操作失败: ' + error.message);
            }
        });

        Dom.btnSkip.addEventListener('click', async function () {
            var currentStep = OnboardingState.currentStep;

            try {
                await skipOnboardingStep(currentStep);

                if (currentStep === 3) {
                    // 跳过最后一步，跳转到仪表盘
                    showSuccess('配置完成！正在跳转到仪表盘...');
                    setTimeout(function () {
                        window.location.href = '/';
                    }, 1500);
                } else {
                    switchToStep(currentStep + 1);
                }
            } catch (error) {
                showError('操作失败: ' + error.message);
            }
        });
    }

    // ==================== 启动 ====================
    document.addEventListener('DOMContentLoaded', init);
})();