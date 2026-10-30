---
name: setup
description: 检查网页导入 Pages 插件在当前会话的 Browser、Pages、图片文件与执行能力，并解释需要补齐的连接。用于安装后设置或导入前能力排查。
---

# Set up Browser to Pages

Discover the current host's available tools and skill resources. Check these capabilities without creating test Pages, uploading user data, changing permissions or navigating unrelated sites:

1. A Browser session/tool that can read the intended source, including any necessary source login in that actual session.
2. Pages tools that can resolve/read the chosen parent, create child Pages, upload image attachments and edit/read back the result.
3. A task workspace/file service that can materialize image files accessible to the attachment uploader. For scripts, identify an available Python 3/JavaScript executor; those may run in a cloud task environment rather than on the phone.
4. For resume across tasks/devices, identify an authorized persistent job store. Do not assume task-local files or desktop sessions automatically sync.

State which checks are established and which remain unverified. If a required capability is missing, name it and use available plugin discovery where supported. Do not fabricate plugin/app IDs, tool schemas, installation success or browser access. Do not represent GitHub publication as account installation.

If the user already gave a source and destination and the required tools are available, load the bundled browser-to-pages skill and continue the authorized import without another confirmation. Otherwise report readiness and the minimal missing input. Setup alone does not authorize importing all course chapters.
