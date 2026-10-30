# Createagle GPT Plugins

Createagle 的 GPT 插件统一分发仓库。每个插件有独立目录和版本，后续插件也通过本仓库更新。

| 插件 | 版本 | 功能 |
| --- | --- | --- |
| [网页导入 Pages](plugins/browser-to-pages) | 0.1.0 | 文章与课程导入、代码保留、图片附件、批量与断点续传 |

## 在 ChatGPT 工作区导入

拥有相应管理权限时，在 **Admin → Plugins → Add → Import marketplace** 中填写：

- Source：`https://github.com/createagle/gpt-plugin`
- Path：留空
- Branch：`main`

导入后配置插件的可用角色及所需连接，再在新会话中使用插件。后续插件通过同一个 marketplace 源分发，更新同步受 ChatGPT 工作区设置控制。[GitHub 导入与同步说明](https://learn.chatgpt.com/docs/enterprise/plugin-management)

手机端应使用工作区已导入并启用的插件。把代码推送到 GitHub，或仅安装本地 skill，都不会自动完成账户安装。插件中的 skill 可分发到支持的 ChatGPT 客户端，实际任务还需要当前环境提供 Browser、Pages 和文件处理能力；手机不会自动继承电脑浏览器的登录态。[Skills 与平台支持](https://learn.chatgpt.com/docs/build-skills)

如果账户没有上述管理入口，这条工作区导入路径不可用；仓库本身不会绕过账户权限，也不代表插件已经上架公开插件目录。

## 在 Codex 添加分发源

```sh
codex plugin marketplace add createagle/gpt-plugin
```

之后在支持的客户端插件目录中安装 `browser-to-pages`。[插件打包与 marketplace](https://developers.openai.com/plugins/build/plugins)

## 开发和分发

```text
.agents/plugins/marketplace.json
plugins/<plugin-name>/plugin.json
plugins/<plugin-name>/skills/<skill-name>/SKILL.md
scripts/
tests/
```

新增插件时复制这套目录约定，注册 marketplace 条目，使用独立语义版本并更新本表。不要把用户内容、账号信息或运行缓存放进仓库。

```sh
python3 scripts/validate_catalog.py
python3 -m unittest discover -s tests
node --test tests/*.test.mjs
python3 scripts/package_plugins.py
```

最后一条命令在 `dist/` 生成每个插件的独立 ZIP；CI 也提供 ZIP 下载产物。GitHub 源用于工作区同步，ZIP 用于支持上传插件包的流程。两者都不等于自动公开发布。
