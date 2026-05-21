# 鸣谢

本项目在开发过程中参考或兼容了以下开源项目与工具，在此表示感谢。

## sub2api

- **项目**：[Wei-Shaw/sub2api](https://github.com/Wei-Shaw/sub2api)
- **说明**：[sub2api](https://github.com/Wei-Shaw/sub2api) 是开源 AI API 网关与账号管理平台。本项目**并非** sub2api 的分支或官方衍生版，仅在以下方面受其启发或保持格式兼容：
  - **导出格式**：支持生成 sub2api 可导入的 `sub2api.json` 账号结构。
  - **OAuth 检测**：账号连通性测试的请求头与流程参考 sub2api 的 OpenAI 账号测试思路（见 `core/account_tester.py` 注释）。
  - **Codex OAuth**：部分授权与 token 刷新逻辑参考 sub2api 的 Codex CLI 相关实现（见 `core/openai_oauth.py` 注释）。
- **许可证**：sub2api 使用其仓库中所示的开源许可证；使用 sub2api 软件请遵循其原项目协议。本仓库代码以 [MIT](../LICENSE) 发布。

## GPTSession 转换参考

- **页面**：[GPTSession2CPAandSub2API](https://gtxx3600.github.io/GPTSession2CPAandSub2API/)
- **说明**：批量 Session 转 CPA / sub2api 等格式的思路见 `tools/session_json_converter.py` 文件头注释。

## 其它依赖

| 组件 | 用途 |
|------|------|
| [Flask](https://flask.palletsprojects.com/) | Web 服务 |
| [curl_cffi](https://github.com/yifeikong/curl_cffi) | 浏览器指纹 HTTP 请求 |
| [pyotp](https://github.com/pyauth/pyotp) | 2FA |
| [requests](https://requests.readthedocs.io/) | Outlook 等 HTTP 调用 |
| Node.js + `sentinel/` | OpenAI Sentinel 校验脚本运行环境 |

---

如对署名有补充或更正，欢迎提交 Issue / Pull Request。
