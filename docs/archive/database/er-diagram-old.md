# Gatherly Web ER 图

本文件记录 Gatherly Web「聚场」项目的核心数据库实体关系设计。

## 核心实体

当前项目核心实体包括：

- User：用户
- Activity：活动
- Registration：活动报名记录
- Rating：活动评分记录
- Circle：同好圈
- Post：圈子帖子

## ER 图

```mermaid
erDiagram
    USER ||--o{ ACTIVITY : "发布"
    USER ||--o{ REGISTRATION : "报名"
    ACTIVITY ||--o{ REGISTRATION : "被报名"

    USER ||--o{ RATING : "评分"
    ACTIVITY ||--o{ RATING : "被评分"

    CIRCLE ||--o{ POST : "包含"
    USER ||--o{ POST : "发布"

    USER {
        int id PK
        string username
        string email
        string password_hash
        string avatar
        string bio
        string interest_tags
        boolean is_verified
        float trust_score
        datetime created_at
    }

    ACTIVITY {
        int id PK
        int creator_id FK
        string title
        text description
        datetime start_time
        datetime end_time
        string location
        string district
        int max_participants
        decimal fee
        string interest_tag
        text preparation
        string image_url
        boolean is_official
        datetime created_at
    }

    REGISTRATION {
        int id PK
        int user_id FK
        int activity_id FK
        string status
        datetime registered_at
    }

    RATING {
        int id PK
        int user_id FK
        int activity_id FK
        int organization_score
        int venue_score
        int experience_score
        float average_score
        text comment
        datetime created_at
    }

    CIRCLE {
        int id PK
        string name
        text description
        string interest_tag
        int activity_count
        int post_count
        datetime created_at
    }

    POST {
        int id PK
        int user_id FK
        int circle_id FK
        string title
        text content
        string post_type
        datetime created_at
    }
# 历史归档，仅供参考

> 本文件为旧版 ER 图说明，字段和关系已不再作为当前数据库事实来源。当前 ER 图请以 [../../er-diagram.md](../../er-diagram.md) 和 [../../database-design.md](../../database-design.md) 为准。
