-- Team Collaboration & Performance Evaluation tables
-- Run this SQL in your Supabase SQL editor.

create table if not exists teams (
    id bigserial primary key,
    company_id bigint not null references companies(id) on delete cascade,
    name text not null,
    project_name text not null,
    description text,
    max_capacity integer not null default 10,
    status text not null default 'active' check (status in ('active', 'paused', 'closed')),
    created_at timestamptz default now()
);

create table if not exists team_members (
    id bigserial primary key,
    team_id bigint not null references teams(id) on delete cascade,
    user_id bigint not null references users(id) on delete cascade,
    role text not null check (role in ('Frontend', 'Backend', 'AI/ML')),
    progress_status text not null default 'pending' check (progress_status in ('pending', 'in_progress', 'completed')),
    joined_at timestamptz default now(),
    unique(team_id, user_id)
);

create table if not exists team_messages (
    id bigserial primary key,
    team_id bigint not null references teams(id) on delete cascade,
    sender_id bigint not null references users(id) on delete cascade,
    message text not null,
    created_at timestamptz default now()
);

create table if not exists tasks (
    id bigserial primary key,
    company_id bigint not null references companies(id) on delete cascade,
    team_id bigint not null references teams(id) on delete cascade,
    assigned_to_user_id bigint references users(id) on delete set null,
    title text not null,
    "description" text not null,
    deadline timestamptz,
    status text not null default 'pending' check (status in ('pending', 'in_progress', 'completed', 'blocked')),
    created_at timestamptz default now(),
    updated_at timestamptz default now(),
    completed_at timestamptz
);

create table if not exists activity_logs (
    id bigserial primary key,
    user_id bigint not null references users(id) on delete cascade,
    team_id bigint references teams(id) on delete set null,
    task_id bigint references tasks(id) on delete set null,
    action_type text not null,
    duration_minutes integer,
    details jsonb default '{}',
    created_at timestamptz default now()
);

create table if not exists team_applications (
    id bigserial primary key,
    user_id bigint not null references users(id) on delete cascade,
    team_id bigint not null references teams(id) on delete cascade,
    desired_role text,
    repository_link text,
    manual_rank integer,
    ats_score numeric(5,2) not null default 0,
    github_score numeric(5,2) not null default 0,
    performance_score numeric(5,2) not null default 0,
    total_score numeric(5,2) not null default 0,
    status text not null default 'waitlisted' check (status in ('active', 'waitlisted')),
    rank integer,
    applied_at timestamptz default now(),
    unique(user_id, team_id)
);

-- Migration block for existing deployments where tables already exist.
-- These run safely in Supabase/Postgres and ensure later index statements do not fail.
alter table if exists teams
    add column if not exists max_capacity integer;

alter table if exists teams
    alter column max_capacity set default 10;

update teams
set max_capacity = 10
where max_capacity is null;

alter table if exists teams
    alter column max_capacity set not null;

alter table if exists teams
    add column if not exists status text;

update teams
set status = 'active'
where status is null;

alter table if exists teams
    alter column status set default 'active';

alter table if exists teams
    alter column status set not null;

do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conname = 'teams_status_check'
    ) then
        alter table teams
            add constraint teams_status_check
            check (status in ('active', 'paused', 'closed'));
    end if;
end $$;

alter table if exists team_applications
    add column if not exists manual_rank integer;

alter table if exists team_applications
    add column if not exists repository_link text;

alter table if exists team_members
    add column if not exists progress_status text;

update team_members
set progress_status = 'pending'
where progress_status is null;

alter table if exists team_members
    alter column progress_status set default 'pending';

alter table if exists team_members
    alter column progress_status set not null;

do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conname = 'team_members_progress_status_check'
    ) then
        alter table team_members
            add constraint team_members_progress_status_check
            check (progress_status in ('pending', 'in_progress', 'completed'));
    end if;
end $$;

create index if not exists idx_teams_company_id on teams(company_id);
create index if not exists idx_team_members_team_id on team_members(team_id);
create index if not exists idx_team_members_user_id on team_members(user_id);
create index if not exists idx_team_messages_team_id on team_messages(team_id);
create index if not exists idx_tasks_team_id on tasks(team_id);
create index if not exists idx_tasks_assigned_to_user_id on tasks(assigned_to_user_id);
create index if not exists idx_activity_logs_user_id on activity_logs(user_id);
create index if not exists idx_team_applications_team_id on team_applications(team_id);
create index if not exists idx_team_applications_user_id on team_applications(user_id);
create index if not exists idx_team_applications_status on team_applications(status);
create index if not exists idx_team_applications_rank on team_applications(team_id, rank);
create index if not exists idx_team_applications_manual_rank on team_applications(team_id, manual_rank);
