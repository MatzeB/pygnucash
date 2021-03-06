.read Inputs/minimal.sql

BEGIN TRANSACTION;
INSERT INTO accounts VALUES('faf269b82570de314625c7d6d887c472','Bank','BANK','a8e71003563f3a753af1fa30628dd5b8',100,0,'553550669ae21fbb5e1211ea8da8d051','','',0,0);
INSERT INTO accounts VALUES('a6c170dc935630c8fd8249b07e9628ab','Income','INCOME','a8e71003563f3a753af1fa30628dd5b8',100,0,'553550669ae21fbb5e1211ea8da8d051','','',0,0);
INSERT INTO accounts VALUES('c1f7d8cabb81e8cffb817fdeb1a6bccf','Expenses','LIABILITY','a8e71003563f3a753af1fa30628dd5b8',100,0,'553550669ae21fbb5e1211ea8da8d051','','',0,0);

INSERT INTO commodities VALUES('a8e71003563f3a753af1fa30628dd5b8','CURRENCY','USD','US Dollar','840',100,1,'currency','');

INSERT INTO transactions VALUES('25c0ba1816c85f4db2b6103bb20e0b41','a8e71003563f3a753af1fa30628dd5b8','','2011-01-01 10:59:00','2017-12-19 05:26:55','Salary');
INSERT INTO transactions VALUES('3b11058d312816673bf3d75def31d734','a8e71003563f3a753af1fa30628dd5b8','','20120202105900','20171219052803','Rent');

INSERT INTO splits VALUES('a52ad22f84761a63f6e23425bf800d87','25c0ba1816c85f4db2b6103bb20e0b41','faf269b82570de314625c7d6d887c472','','','n','19700101000000',11100,100,11100,100,NULL);
INSERT INTO splits VALUES('a12285d7f4ef38bf85a996828234af1f','25c0ba1816c85f4db2b6103bb20e0b41','a6c170dc935630c8fd8249b07e9628ab','','','n','19700101000000',-11100,100,-11100,100,NULL);
INSERT INTO splits VALUES('38039e1b97b6c5faa7cdee9e2b778611','3b11058d312816673bf3d75def31d734','faf269b82570de314625c7d6d887c472','','','n','19700101000000',-6600,100,-6600,100,NULL);
INSERT INTO splits VALUES('a48bbb9b3f9e158f218b5c81c69d5681','3b11058d312816673bf3d75def31d734','c1f7d8cabb81e8cffb817fdeb1a6bccf','','','n','19700101000000',6600,100,6600,100,NULL);

COMMIT;
