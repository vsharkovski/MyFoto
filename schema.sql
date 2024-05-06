drop table if exists comments;
drop table if exists photo_tags;
drop table if exists tags;
drop table if exists photos;
drop table if exists friends;
drop table if exists albums;
drop table if exists users;

create table users (
    user_id serial primary key,
    first_name varchar(32) not null,
    last_name varchar(32) not null,
    hometown varchar(64) not null,
    gender varchar(16) not null,
    email varchar(64) not null,
    birth_date date,
    password varchar(64) not null,
    unique (email),
    check (length(password) >= 10)
);

create table friends (
    user1_id serial not null,
    user2_id serial not null,
    primary key (user1_id, user2_id),
    foreign key (user1_id) references users (user_id) on delete cascade,
    foreign key (user2_id) references users (user_id) on delete cascade,
    check (user1_id != user2_id)
);

create table albums (
    album_id serial primary key,
    name varchar(64) not null,
    creation_date date not null,
    owner_id serial not null,
    foreign key (owner_id) references users (user_id) on delete cascade
);

create table photos (
    photo_id serial primary key,
    caption varchar (256) not null,
    filename varchar (4096) not null,
    album_id serial not null,
    foreign key (album_id) references albums (album_id) on delete cascade
);

create table comments (
    comment_id serial primary key,
    text varchar (4096) not null,
    creation_date date not null,
    photo_id serial,
    user_id serial,
    foreign key (photo_id) references photos (photo_id) on delete cascade,
    foreign key (user_id) references users (user_id) on delete cascade
);

create table tags (
    label varchar (32) primary key,
    -- Must contain only lowercase alphabetical characters (and obviously no spaces)
    check (label ~* '^[a-z]+$')
);

create table photo_tags (
    photo_id serial not null,
    tag_label varchar (32) not null,
    primary key (photo_id, tag_label),
    foreign key (photo_id) references photos (photo_id) on delete cascade,
    foreign key (tag_label) references tags (label) on delete cascade
);

create table likes (
    user_id serial not null,
    photo_id serial not null,
    primary key (user_id, photo_id),
    foreign key (user_id) references users on delete cascade,
    foreign key (photo_id) references photos on delete cascade
);
