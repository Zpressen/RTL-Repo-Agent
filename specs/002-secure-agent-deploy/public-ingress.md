# 公网入口接入记录

2026-10-19，服务器 `39.107.243.176`。

当前入口为 <https://agent.deepvalleychip.cn>，按用户要求免网站登录密码。浏览器直接访问公网域名，无需 SSH 隧道；网页和 Agent 问答均运行于服务器。

同日按用户要求从 design 切换至 agent。新域名已解析到 `39.107.243.176`，HTTPS 校验通过。用户随后要求 design 保留原页面，现已恢复 `/srv/deepvalleychip/design/index.html` 静态站，不再跳转。后台仅接受 agent 的 HTTPS Origin。此前的 301 属于历史配置，浏览器若仍跳转可用无痕窗口或清除旧站点缓存。

新域名实际浏览器验证四案例、输入/草稿、真实波形、Secure Cookie、来源/大小边界和真实问答通过；问答 13.302 秒完成，有一条有效证据引用。证据为私有 `agent-domain-browser.json/.png`，下文原 design 入口的早期验收资料继续保留。

这次也查明了此前偶发 502 的根因：`vcdvcd` 在 import 时将 SIGPIPE 改为默认终止，服务遇到断管可能以信号 13 退出。`waveform.py` 现保存并恢复应用原有的信号设置，不修改第三方库或波形语义。新增子进程测试先复现退出码 -13，再验证修复；目标 API 实际接收 SIGPIPE 后仍存活且 health=200。完整 Web 回归 105 项通过。该修复使先前“暂时不能复现”的 502 有了明确根因及回归证据。

## 实际路由与服务

```text
浏览器 HTTPS → Caddy :443 → 127.0.0.1:18080 → Demo 页面 / API
```

Caddy 将 agent 站点代理到回环后台，design 独立提供原静态页面；主站/www 配置和 `/srv` 两份原页面不变。新页面由后台发布目录的构建产物提供，Caddy 不读取用户 HOME，也不持有模型密钥。KG 仍只监听 `127.0.0.1:17687`；后台没有新增公网端口。

- 后台单位：`rtl-demo-public.service`，已 enable，运行身份 dev。
- 后台目录：`/home/dev/rtl-agent-demo/releases/ssh-demo-20261016-r1/`。
- 私有配置：`/home/dev/rtl-agent-demo/private/config.yaml`，`access_mode: public`、`development: false`，Origin 仅允许正式 HTTPS 域名，Cookie 启用 Secure/HttpOnly。
- 受限问答：显式 `runtime.bounded_chat: true`，API/问答解释器保留 384 MiB 地址空间硬限制、全局单问答、namespace 和发送前内存余量检查；API 服务另有实际 cgroup v1 `MemoryLimit=256M`、CPUQuota=100%、TasksMax=128。该预算不放开 native worker。
- 旧 gateway cron 恢复段已移除，避免与 systemd 重复启动；KG/worker 的独立恢复段保留。

Caddy 2.6.4 的代理可能把请求体超限的内部 413 包装为 502。本次只对包含该明确超限原因的错误映射回 413，其余代理故障保持原状态；20,000 字节限制和 API 实际流长度检查均保留。配置先验证再热加载；原始 Caddyfile 保存在 root 私有恢复目录。

## 已验证

无登录凭据的真实浏览器直接访问公网 HTTPS：四案例输入框可编辑、刷新保留草稿、真实 DUT/参考波形可见；E203 修复前可定位 1125 ps，修复后显示 0/222。Secure/HttpOnly Cookie 生效，跨来源 POST 返回 403，超长请求返回 413。

真实公网问答最小场景两轮分别 11.830 秒、10.729 秒完成，状态均为 answered，各带一个有效证据引用。没有 API 替身或关闭 TLS 校验。私有摘要与截图保存于 `.rtl-demo/deployment/public-chat-only.json/.png`，完整浏览流程另存 `public-ingress-browser.json/.png`。

完整流程最终也通过：先切换四案例、查看波形和刷新草稿，再进行两轮真实问答，分别 10.145 秒、21.845 秒完成，各带一个有效证据引用，无页面异常。切换调试阶段曾出现一次提交 502；没有将该失败记为成功，重启并启用退出码/故障栈诊断后的最小场景与完整场景均通过。

Web 回归 103 项通过。此次接入没有完成整机重启、完整生成/修复或所有正式部署 SC 验收，不将其登记为完整 accepted。

受控停止 gateway 子进程后，11.508 秒内自动恢复；该时间包括原进程的优雅退出等待。恢复窗口有短暂页面失败，恢复后主站/www/design/API/CAD 均为 HTTP 200；原记录保留。API 内核内存限制已实际核验为 268,435,456 字节，演练期间无 OOM 或内存限额命中。

## 运维与回退

```bash
ssh dev@39.107.243.176
sudo systemctl status rtl-demo-public.service --no-pager
sudo systemctl restart rtl-demo-public.service
sudo systemctl status caddy --no-pager
curl -I https://agent.deepvalleychip.cn
curl https://agent.deepvalleychip.cn/api/health
```

gateway 子进程的日志和退出信息在 `/home/dev/rtl-agent-demo/control/gateway.log`、`gateway-exit.json`；systemd 单位日志使用 `journalctl -u rtl-demo-public.service`。状态、日志可能含内部路径，不作为网页静态文件公开。

维护者如需恢复到接入前的静态 design：

```bash
sudo python3 /root/rtl-demo-ingress/connect-public-ingress.py rollback
```

该 root 所有的脚本只恢复备份 Caddyfile、校验并热加载，不回退 Store、消息或模型配置。原始备份为 `/var/lib/rtl-demo-ingress/Caddyfile.before-1792395561`。本轮未执行实际回退，不将其登记为回退演练通过。

## 保留的执行限制

网页已可浏览历史波形并进行真实模型问答。现场复验、生成和自动修复仍会因完整内存预算、worker 的有效 cgroup 与限容量执行卷未通过而明确拒绝。API 服务的 cgroup 不等于 worker 的执行边界；不得用这次公网路由接入替代 [执行环境记录](runtime-environment.md) 中保留的检查。
