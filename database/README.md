# 手作集数据库

开发环境使用 SQLite，生产环境可将同一关系模型迁移至 PostgreSQL。金额字段统一以分存储；图片和视频只保存对象存储键与公开 URL，不将二进制媒体写入数据库。

## 初始化

```powershell
python database/init_db.py
```

这会创建 `database/handicrafts.db`，依次执行所有迁移和种子数据。脚本可以重复执行，迁移由 `schema_migrations` 表记录。

## 浏览器推送通知

生产服务器安装依赖后生成一次 VAPID 密钥，并将输出写入后端进程的环境变量。私钥只能保存在服务器，不能提交到 Git。

```powershell
pip install -r requirements.txt
python database/generate_vapid_keys.py
```

站点必须使用 HTTPS。卖家登录工作台后点击“开启浏览器消息通知”并允许浏览器权限；之后网页关闭时也能收到买家消息通知。

## 迁移旧版本地作品

```powershell
python database/server.py
```

启动服务后，以卖家身份进入“店主工作台 → 我的作品”，点击“迁移本地作品”。迁移会将当前浏览器会话中的已发布作品、下架状态、草稿、规格、图片和视频引用写入 SQLite；同一卖家重复迁移会更新既有记录，不会重复创建作品。】【

旧版图片和视频若为浏览器内的 `data:` 地址，会原样迁入媒体 URL 字段。正式环境应在迁移后将这些媒体上传到对象存储并替换为公开 URL。

## 角色边界

买家：地址、购物车、订单、售后和评价。

卖家：认证资料、店铺、商品草稿/上架状态、规格 SKU、媒体、发货、售后处理和评价回复。
