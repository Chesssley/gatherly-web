# Gatherly Database Design

This document records the database foundation added for TASK-05. The current
routes still use temporary in-memory `activities` and `circles` data in
`app.models`, so these models are prepared for later route integration without
changing the existing page behavior.

## Preserved Core Models

- `User`: account, role, trust score, and profile-related relationships.
- `Activity`: activity base data and organizer relationship.
- `Registration`: user activity registration records.
- `Circle`: interest circle base data.
- `Post`: circle post base data.
- `Review` and `Rating`: kept as compatibility models because current route
  code still references them.

## New Models

- `ActivityReview`: activity scoring table for future US-09 work.
  - One user can review one activity once.
  - Unique constraint: `activity_id`, `reviewer_id`.
  - Stores organization, venue, experience, average score, comment, and status.

- `UserReview`: participant-to-participant review table.
  - One reviewer can review the same participant once per activity.
  - Unique constraint: `activity_id`, `reviewer_id`, `reviewee_id`.

- `TrustScoreLog`: append-only trust score change history.
  - Stores score before/after, delta, reason, related object, and operator.

- `CircleMember`: circle role and membership table.
  - Supports `owner`, `admin`, and `member` roles.
  - Unique constraint: `circle_id`, `user_id`.

- `Comment`: unified comments for activities and circle posts.
  - Exactly one target must be set: `activity_id` or `post_id`.
  - Supports threaded replies through `parent_id`.

- `Interaction`: generic user interactions.
  - Supports `like`, `favorite`, and `share`.
  - Unique constraint: `user_id`, `target_type`, `target_id`, `action_type`.

- `ProfileVisibility`: personal profile visibility settings.
  - One visibility config per user.
  - Unique constraint: `user_id`.

- `AdminLog`: admin operation log.
  - Stores operator, action, target, detail, IP address, and timestamp.

## Future US-09 Integration Notes

US-09 activity rating work should migrate route and template logic from the
compatibility `Rating` model to `ActivityReview`.

Recommended steps:

1. Replace `Rating` imports in `app/routes/activity.py` with `ActivityReview`.
2. Query stats from `ActivityReview.organization_score`,
   `ActivityReview.venue_score`, `ActivityReview.experience_score`, and
   `ActivityReview.average_score`.
3. Check duplicate submissions with
   `ActivityReview.query.filter_by(activity_id=activity_id, reviewer_id=user_id)`.
4. Create `ActivityReview` rows after validating registration eligibility and
   score range.
5. Keep the current unique constraint as the final guard against duplicate
   activity reviews.

