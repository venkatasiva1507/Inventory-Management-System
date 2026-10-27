create database if not exists inventory_db;
use inventory_db;

create table if not exists products(
product_id int auto_increment primary key,
name varchar(100) not null unique,
category varchar(100) not null,
quantity decimal(10,2) not null default 0,
cost_price decimal(10,2) not null,
selling_price decimal(10,2) not null);

create table if not exists customers(
customer_id int auto_increment primary key,
name varchar(100) not null unique);

create table if not exists orders(
order_id int auto_increment primary key,
customer_id int not null,
total_amount decimal(12,2) not null default 0,
order_date timestamp default current_timestamp,
foreign key (customer_id) references customers(customer_id));

create table if not exists order_items(
order_item_id int auto_increment primary key,
order_id int not null,
product_id int not null,
product_name varchar(100) not null,
quantity decimal(10,2) not null,
selling_price decimal(10,2) not null,
line_total decimal(12,2) not null,
foreign key (order_id) references orders(order_id),
foreign key(product_id) references products(product_id));

select * from products;
select * from customers;
select * from orders;
select * from order_items;


alter table products add column category varchar(100) not null default 'general';