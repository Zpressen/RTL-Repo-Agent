## Neo4j 入库（RTL KG）

### 1) 启动 Neo4j（Docker）
```bash
conda activate RTL-Agent
cd /home/mokita/RPG-ZeroRepo
docker compose -f zerorepo/rtl_impl/rtl_kg/docker-compose.dev.yml up -d
```
打开浏览器：`http://localhost:7474`，账号/密码：`neo4j / neo4j123456`（可在 compose 里改）。

### 2) 安装 Python 依赖
```bash
pip install neo4j
```

### 3) 入库
```bash
cd /home/mokita/RPG-ZeroRepo
python -m zerorepo.rtl_impl.rtl_kg.ingest_rtl_kg_to_neo4j \
  --repo /path/to/your/rtl/repo \
  --neo4j-uri bolt://localhost:7687 \
  --neo4j-user neo4j \
  --neo4j-pass neo4j123456 \
  --mode full
```
也可直接运行脚本：
```bash
python zerorepo/rtl_impl/rtl_kg/ingest_rtl_kg_to_neo4j.py \
  --repo /path/to/your/rtl/repo \
  --neo4j-uri bolt://localhost:7687 \
  --neo4j-user neo4j \
  --neo4j-pass neo4j123456 \
  --mode full
```

### 数据库删除
只删当前 repo 的分区数据：
```cypher
MATCH (n {repo_uid: "<repo_name>@<commit_sha>"}) DETACH DELETE n;
```

如果不确定 repo_uid，可以先查有哪些：
```cypher
MATCH (n) RETURN n.repo_uid AS repo_uid, count(*) AS c ORDER BY c DESC;
```

查询仓库：
```cypher
MATCH (n {repo_uid: "RPG-ZeroRepo@417611883d06"})
RETURN n
LIMIT 100;
```
