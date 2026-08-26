import pandas as pd
def process_student_scores(input_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    读取小学学生成绩表，清除空行，计算绩优等级，并按性别汇总各科平均分。
    参数：
        input_path: 输入 Excel 文件路径
    返回：
        cleaned_df: 清洗并添加“总分”“平均分”“绩优”后的明细数据
        gender_summary_df: 按性别汇总后的平均分数据
    """
    # 读取 Excel 文件
    df = pd.read_excel(input_path)
    # 删除整行均为空的数据
    df = df.dropna(how="all").copy()
    # 定义各科列名
    subject_columns = ["语文", "数学", "英语", "科学"]

    # 确保各科成绩为数值类型；无法转换的内容处理为缺失值
    df[subject_columns] = df[subject_columns].apply(
        pd.to_numeric,
        errors="coerce"
    )
    # 计算每位学生的总分和平均分
    df["总分"] = df[subject_columns].sum(axis=1)
    df["平均分"] = df[subject_columns].mean(axis=1)
    # 根据平均分划分绩优等级
    def get_performance_level(avg_score):
        if pd.isna(avg_score):
            return pd.NA
        if avg_score > 90:
            return "A+"
        if avg_score >= 80:
            return "A"
        if avg_score >= 70:
            return "B+"
        if avg_score >= 60:
            return "B"
        if avg_score >= 50:
            return "C"
        return pd.NA

    df["绩优"] = df["平均分"].apply(get_performance_level)

    # 按性别统计人数、各科平均分及总平均分
    gender_summary_df = (
        df.groupby("性别", dropna=False)
        .agg(
            学生人数=("性别", "size"),
            语文平均分=("语文", "mean"),
            数学平均分=("数学", "mean"),
            英语平均分=("英语", "mean"),
            科学平均分=("科学", "mean"),
            总平均分=("平均分", "mean"),
        )
        .reset_index()
    )

    # 平均分保留 1 位小数
    average_columns = [
        "语文平均分",
        "数学平均分",
        "英语平均分",
        "科学平均分",
        "总平均分",
    ]
    gender_summary_df[average_columns] = gender_summary_df[average_columns].round(1)

    return df, gender_summary_df

    # 在score_process.py文件的最底部，新增这一段
if __name__ == "__main__":
        input_file = "小学学生成绩表.xlsx"   # ✅这里就是Excel文件名
        cleaned_df, gender_summary_df = process_student_scores(input_file)

        # 输出结果文件
        cleaned_df.to_excel("处理后明细.xlsx", index=False)
        gender_summary_df.to_excel("性别汇总统计.xlsx", index=False)
        print("处理完成，已生成输出excel")