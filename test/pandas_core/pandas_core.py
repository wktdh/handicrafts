import pandas as pd

# ---------------------- 模拟两张业务表（电商场景） ----------------------
# 订单主表：订单号、用户、商品ID、实付、下单时间
order_data = [
    {"order_id":"O001","user":"张三","goods_id":"G01","pay":128},
    {"order_id":"O002","user":"李四","goods_id":"G02","pay":89},
    {"order_id":"O003","user":"王五","goods_id":"G01","pay":128},
    {"order_id":"O004","user":"赵六","goods_id":"G03","pay":199},
    {"order_id":"O005","user":"钱七","goods_id":"G02","pay":89},
]
df_order = pd.DataFrame(order_data)

# 商品维度表：商品ID、商品名称、类目、成本
goods_data = [
    {"goods_id":"G01","goods_name":"手工铜丝耳环","category":"首饰","cost":35},
    {"goods_id":"G02","goods_name":"编织挂件","category":"配饰","cost":22},
    {"goods_id":"G03","goods_name":"风动装饰画","category":"家居","cost":80},
]
df_goods = pd.DataFrame(goods_data)

print("===订单表===")
print(df_order)
print("\n===商品表===")
print(df_goods)


# ====================== 1. concat 表合并（上下堆叠，行增加）======================
# 场景：把1月订单、2月订单两个表，上下拼在一起，行数变多，列不变
order_extra = pd.DataFrame([
    {"order_id":"O006","user":"孙八","goods_id":"G03","pay":199}
])

# pd.concat([表1,表2])  上下合并
df_concat = pd.concat([df_order, order_extra], ignore_index=True)
print("\n=====concat上下合并(堆叠行)=====")
print(df_concat)
# ignore_index=True：合并之后重新生成行号，不然旧行号会重复


# ====================== 2. merge join 表关联（左右拼接，列增加，SQL的JOIN）======================
# 业务：订单表只有goods_id，想要把【商品名称、类目、成本】匹配到每一行订单上
# on=关联键，两张表共有的字段：goods_id

# inner join：两边都存在的数据才保留（交集）
df_inner = pd.merge(df_order, df_goods, on="goods_id", how="inner")
print("\n===== inner join 内连接 ======")
print(df_inner)

# left join 左连接【电商最常用！！】
# 左边订单表全部保留；商品表匹配不到的字段填充NaN。防止商品基础资料缺失丢订单数据
df_left = pd.merge(df_order, df_goods, on="goods_id", how="left")
print("\n===== left join 左连接（工作最常用）=====")
print(df_left)

'''
how参数4种：
how="inner"   内连接：两边都有才保留
how="left"    左连接：左表全部保留，右表匹配
how="right"   右连接
how="outer"   全外连接，全部保留
电商90%场景使用 left join
'''


# ======================3. groupby 分组统计（面试重中之重）======================
# 使用上面left join之后的完整表 df_left
# 场景：按类目分组，统计订单数量、销售额、平均售价

print("\n===== groupby 分组统计 按category类目=====")
group_result = df_left.groupby("category").agg(
    订单数量=("order_id", "count"),
    销售总金额=("pay", "sum"),
    平均售价=("pay", "mean")
).reset_index()

print(group_result)
# reset_index()：把分组索引变回普通列，否则category会变成行索引，输出excel很别扭

# 多重分组：先按类目，再按商品名称分组
print("\n====多重groupby 类目+商品名称=====")
multi_group = df_left.groupby(["category","goods_name"]).agg(
    订单数=("order_id","count"),
    营收=("pay","sum")
).reset_index()
print(multi_group)
