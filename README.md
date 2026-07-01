# 千篇万律·美食地图（广州站）🍽️

法律人专属广州美食地图 —— 聚焦「商务宴请」「同行休闲聚餐」两大场景。

🌐 **在线地图**: [kevinshao713-ux.github.io/gz-food-map](https://kevinshao713-ux.github.io/gz-food-map)

## 功能

- 🗺️ 交互式地图，按场景/菜系/人均筛选
- 📋 列表视图，微信内直接浏览
- ⚠️ 排雷标记，避坑预警
- 📱 移动端适配，微信扫码即看
- 📝 飞书表单提交，群友零门槛推荐

## 数据来源

群友通过飞书表单提交推荐 → 管理员审核补全 → 自动同步到地图。

## 项目结构

```
gz-food-map/
├── index.html        # 美食地图网站（单文件）
├── restaurants.js    # 餐厅数据
├── sync.py           # 数据同步脚本（飞书→JS）
└── README.md
```

## 维护指南

### 添加新餐厅

1. 群友通过飞书表单提交（店名+地址+场景+推荐语）
2. 管理员在飞书多维表格中补全信息（人均/菜系/推荐菜）
3. 运行同步脚本：

```bash
# 安装依赖（仅首次）
pip install -r requirements.txt  # 如有

# 同步数据（需已登录飞书）
python sync.py

# 提交更新
git add restaurants.js
git commit -m "更新餐厅数据"
git push
```

### 自动补全坐标

设置高德地图 API Key 后，sync.py 会自动将地址转为经纬度：

```bash
set GAODE_KEY=你的key
python sync.py
```

免费申请：[高德开放平台](https://lbs.amap.com/api/webservice/guide/create-project/get-key)

## 技术栈

- Leaflet.js — 开源地图库
- 高德瓦片 — 国内地图免费瓦片
- GitHub Pages — 免费托管
- 飞书多维表格 — 数据后台
