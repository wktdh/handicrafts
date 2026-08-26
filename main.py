from crewai import Agent, Task, Crew, LLM
from dotenv import load_dotenv
import os

load_dotenv()

llm = LLM(
    model="openai/gpt-5.6-terra",
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
    temperature=0.7
)

researcher = Agent(
    role="跨境市场研究员",
    goal="搜集海外手工饰品市场信息",
    backstory="跨境行业分析师",
    verbose=True,
    llm=llm
)

copywriter = Agent(
    role="英文独立站文案",
    goal="根据市场调研结果，写出一篇英文独立站文案",
    backstory="擅长Etsy、独立站产品描述，懂海外消费者话术",
    verbose=True,
    llm=llm
)

tast1 = Task(
    description="调研铜丝钩织饰品海外市场，输出调研摘要",
    agent=researcher,
    expected_output="markdown调研摘要"
)

tast2 = Task(
    description="参考上面的调研结果，生成3套英文产品标题+产品描述",
    agent=copywriter,
    expected_output="3组标题+描述，适合独立站上架"
)

crew = Crew(agents=[researcher, copywriter], tasks=[tast1, tast2])
result = crew.kickoff()
print("\n====输出结果====")
print(result.raw)