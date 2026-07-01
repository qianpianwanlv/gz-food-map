#!/usr/bin/env python3
"""
千篇万律·美食地图 —— 数据同步脚本
从飞书多维表格拉取数据 → 生成 restaurants.js → 高德API补坐标

用法:
  python sync.py

前置条件:
  1. 已安装 lark-cli 并登录 (npx lark-cli auth login)
  2. 已配置高德地图 Web服务 API Key（用于地址→经纬度转换）
     设置环境变量: set GAODE_KEY=你的key
     或免费申请: https://lbs.amap.com/api/webservice/guide/create-project/get-key
"""

import json, subprocess, os, sys, re, time

BASE_TOKEN = "DlYLbP9eBaNKvBsyy8HcFncynYc"
TABLE_ID = "tbl4A1MiA4uzpQ1q"
OUTPUT_FILE = "restaurants.js"
GAODE_KEY = os.environ.get("GAODE_KEY", "")

# 字段名 → JS字段名映射
FIELD_MAP = {
    "餐厅名称": "name",
    "地址": "address",
    "场景标签": "scene",
    "菜系": "cuisine",
    "人均": "avgPrice",
    "大众评分": "rating",
    "推荐菜": "dishes",
    "电话": "phone",
    "推荐人": "recommender",
    "推荐语": "comment",
    "排雷": "minefield",
    "排雷说明": "minefieldNote",
    "经纬度": None,  # handled separately
    "状态": None,
}


def run_lark(cmd):
    """Run lark-cli command and return JSON"""
    result = subprocess.run(
        ["npx", "lark-cli"] + cmd,
        capture_output=True, text=True, timeout=30
    )
    # lark-cli outputs JSON to stdout, but may have warnings to stderr
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except:
                pass
    # Try parsing the whole output
    try:
        return json.loads(result.stdout.strip())
    except:
        print(f"lark-cli error: {result.stderr}")
        sys.exit(1)


def fetch_records():
    """从飞书多维表格获取所有记录"""
    print("📡 正在从飞书拉取数据...")
    result = run_lark([
        "base", "+record-list",
        "--base-token", BASE_TOKEN,
        "--table-id", TABLE_ID,
        "--format", "json"
    ])

    if not result.get("ok"):
        print(f"❌ 拉取失败: {result}")
        sys.exit(1)

    records = result.get("data", {}).get("data", [])
    fields_info = result.get("data", {}).get("fields", [])
    print(f"✅ 获取到 {len(records)} 条记录")

    # Build field name → id reverse map from fields info
    # The API returns field names as keys in records

    return records


def geocode(address, name=""):
    """用高德API将地址转换为经纬度。优先POI搜索，避免地址歧义"""
    if not GAODE_KEY:
        return None, None

    import urllib.request, urllib.parse

    # 方法一：用餐厅名做POI搜索（最准，不会串到同名分店）
    if name:
        params = urllib.parse.urlencode({
            "key": GAODE_KEY,
            "keywords": name,
            "city": "广州",
            "output": "JSON",
            "offset": 3
        })
        url = f"https://restapi.amap.com/v3/place/text?{params}"
        try:
            req = urllib.request.urlopen(url, timeout=10)
            data = json.loads(req.read().decode())
            if data["status"] == "1" and data["pois"]:
                loc = data["pois"][0]["location"]
                lng, lat = loc.split(",")
                print(f"    ↳ POI搜索命中: {data['pois'][0]['name'][:30]}")
                return float(lat), float(lng)
        except Exception:
            pass

    # 方法二：地址反查，自动简化过细地址
    candidates = [address]
    simplified = re.sub(r'[（(][^)）]*[)）]', '', address).strip()
    if simplified != address:
        candidates.append(simplified)
    stripped = re.sub(r'[负地].{0,3}[层楼].{0,6}(铺|号|室)', '', simplified).strip()
    if stripped != simplified:
        candidates.append(stripped)

    for addr in candidates:
        params = urllib.parse.urlencode({
            "key": GAODE_KEY,
            "address": addr,
            "city": "广州",
            "output": "JSON"
        })
        url = f"https://restapi.amap.com/v3/geocode/geo?{params}"
        try:
            req = urllib.request.urlopen(url, timeout=10)
            data = json.loads(req.read().decode())
            if data["status"] == "1" and data["geocodes"]:
                loc = data["geocodes"][0]["location"]
                lng, lat = loc.split(",")
                return float(lat), float(lng)
        except Exception:
            continue

    print(f"  ⚠️ 地理编码失败: {address[:30]}...")
    return None, None


def transform_records(records):
    """将飞书记录转换为 restaurants.js 格式"""
    restaurants = []

    for record in records:
        # Some APIs return {fields: {...}, id: "..."} format
        if "fields" in record:
            fields = record["fields"]
        else:
            fields = record

        r = {
            "name": "",
            "address": "",
            "scene": "",
            "cuisine": "",
            "avgPrice": 0,
            "rating": None,
            "dishes": "",
            "phone": "",
            "recommender": "",
            "comment": "",
            "minefield": False,
            "minefieldNote": "",
            "lat": None,
            "lng": None,
        }

        for cn_name, js_name in FIELD_MAP.items():
            if js_name is None:
                continue
            val = fields.get(cn_name)
            if val is None:
                continue

            # Handle select fields (returned as arrays)
            if isinstance(val, list) and len(val) > 0:
                val = val[0] if isinstance(val[0], str) else val[0].get("text", str(val[0]))

            # Handle checkbox
            if js_name == "minefield":
                r[js_name] = bool(val)
            elif js_name == "avgPrice":
                try:
                    r[js_name] = int(float(val))
                except:
                    r[js_name] = 0
            elif js_name == "rating":
                try:
                    r[js_name] = round(float(val), 1)
                except:
                    r[js_name] = None
            else:
                r[js_name] = str(val).strip() if val else ""

        # Parse 经纬度 field if exists
        coord_str = fields.get("经纬度", "")
        if coord_str and isinstance(coord_str, str) and "," in coord_str:
            parts = coord_str.split(",")
            try:
                r["lat"] = float(parts[0].strip())
                r["lng"] = float(parts[1].strip())
            except:
                pass

        # Geocode if no coordinates
        if (r["lat"] is None or r["lng"] is None) and r["address"] and GAODE_KEY:
            print(f"  🗺️ 正在查询坐标: {r['name'][:30]}...")
            lat, lng = geocode(r["address"], r["name"])
            if lat and lng:
                r["lat"] = lat
                r["lng"] = lng
                print(f"    → ({lat}, {lng})")
            time.sleep(0.2)  # rate limit

        restaurants.append(r)

    return restaurants


def write_js(restaurants):
    """写入 restaurants.js 文件"""
    import datetime
    today = datetime.date.today().strftime("%Y-%m-%d")

    js = f"""// 千篇万律·美食推荐（广州站）
// 数据由群友推荐 + 管理员维护
// 最后更新: {today}

var RESTAURANTS = {json.dumps(restaurants, ensure_ascii=False, indent=2)};
"""

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(js)

    # Count geocoded
    has_coords = sum(1 for r in restaurants if r["lat"] and r["lng"])
    print(f"\n✅ 已写入 {OUTPUT_FILE}")
    print(f"   {len(restaurants)} 家餐厅, {has_coords} 家有坐标")
    if has_coords < len(restaurants):
        print(f"   ⚠️ {len(restaurants) - has_coords} 家缺少坐标，设置 GAODE_KEY 环境变量后重新运行")


def main():
    print("=" * 50)
    print("  千篇万律·美食地图 — 数据同步")
    print("=" * 50)

    if not GAODE_KEY:
        print("💡 提示: 设置高德API Key可自动补全坐标")
        print("   set GAODE_KEY=你的key")
        print("   免费申请: https://lbs.amap.com/api/webservice/guide/create-project/get-key\n")

    records = fetch_records()
    restaurants = transform_records(records)
    write_js(restaurants)

    print("\n🎉 同步完成！现在可以:")
    print("   git add restaurants.js && git commit -m '更新餐厅数据' && git push")


if __name__ == "__main__":
    main()
