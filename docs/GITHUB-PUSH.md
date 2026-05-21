# 一键上传到 GitHub（Windows）

把本地 **Codex凭证管理** 项目同步到：

https://github.com/Aze0920/Codex_Credential_Manager

---

## 一、一次性准备（只需做一次）

### 1. 安装 Git

下载并安装：https://git-scm.com/download/win  

安装时勾选 **Git from the command line**，其余默认即可。

安装后在 cmd 输入 `git --version` 能看到版本号即成功。

### 2. 配置提交者名字（只需一次）

在 cmd 执行（把名字和邮箱改成你的）：

```bat
git config --global user.name "Aze0920"
git config --global user.email "你的GitHub邮箱@example.com"
```

### 3. 配置 GitHub 登录（只需一次）

推送时要能登录 GitHub，推荐 **Personal Access Token（PAT）**：

1. 打开：https://github.com/settings/tokens  
2. **Generate new token (classic)**  
3. Note 填：`Codex push`  
4. 勾选权限：**repo**（完整仓库权限）  
5. 生成后 **复制 Token**（只显示一次，请保存到记事本）

第一次 `git push` 时：

- 用户名：`Aze0920`  
- 密码：粘贴 **Token**（不是 GitHub 登录密码）

Windows 会记住凭据，以后一键推送不用再输。

> 也可安装 [GitHub CLI](https://cli.github.com/) 后执行 `gh auth login`，按提示浏览器登录。

---

## 二、以后每次更新：一键上传

### 方法 A（推荐）：双击脚本

```
scripts\setup-github-once.bat    （首次配置）
scripts\push-to-github.bat       （日常上传）
```

配置脚本使用 PowerShell，避免 cmd 中文乱码。按提示输入时**只填一个词**（不要粘贴整行 git 命令）。

或在项目根目录 cmd：

```bat
scripts\push-to-github.bat
```

脚本会自动：

- 检查是否误含 `.db`、`.env`、`.venv`  
- `git add` + `commit` + `push` 到 `main`  

### 方法 B：自定义提交说明

```bat
scripts\push-to-github.bat -CommitMessage "feat: 添加版本更新功能"
```

---

## 三、推送成功后

1. 打开 https://github.com/Aze0920/Codex_Credential_Manager 确认文件已更新  
2. 若改了根目录 **`VERSION`**，到 **Releases** 新建版本，例如 `v1.0.5`（与 VERSION 一致）  
3. 服务器上执行 `git pull` 或 `./scripts/update-server.sh` 拉取新代码  

---

## 四、常见问题

| 问题 | 处理 |
|------|------|
| `git 不是内部或外部命令` | 未安装 Git 或未加入 PATH，重装 Git |
| `user.name / user.email` | 做上面「第 2 步」 |
| `Authentication failed` | PAT 错误或过期，重新生成 Token |
| `rejected` / `non-fast-forward` | 先在 GitHub 网页是否改过文件；本地执行 `git pull origin main --rebase` 再推送 |
| 推送很慢 | 正常，首次或改动大时会慢 |

---

## 五、不会上传的内容（自动排除）

- `data/*.db`、`data/*.log`（数据库）  
- `.env`（密码）  
- `.venv`（虚拟环境）  

由 `.gitignore` 控制；脚本推送前会再检查一遍。
