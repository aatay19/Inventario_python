-- MySQL dump 10.13  Distrib 8.0.44, for Win64 (x86_64)
--
-- Host: localhost    Database: inventario_test_db
-- ------------------------------------------------------
-- Server version	8.0.44

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Dumping data for table `auth_group`
--

LOCK TABLES `auth_group` WRITE;
/*!40000 ALTER TABLE `auth_group` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_group` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping data for table `auth_group_permissions`
--

LOCK TABLES `auth_group_permissions` WRITE;
/*!40000 ALTER TABLE `auth_group_permissions` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_group_permissions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping data for table `auth_permission`
--

LOCK TABLES `auth_permission` WRITE;
/*!40000 ALTER TABLE `auth_permission` DISABLE KEYS */;
INSERT INTO `auth_permission` VALUES (1,'Can add log entry',1,'add_logentry'),(2,'Can change log entry',1,'change_logentry'),(3,'Can delete log entry',1,'delete_logentry'),(4,'Can view log entry',1,'view_logentry'),(5,'Can add permission',2,'add_permission'),(6,'Can change permission',2,'change_permission'),(7,'Can delete permission',2,'delete_permission'),(8,'Can view permission',2,'view_permission'),(9,'Can add group',3,'add_group'),(10,'Can change group',3,'change_group'),(11,'Can delete group',3,'delete_group'),(12,'Can view group',3,'view_group'),(13,'Can add user',4,'add_user'),(14,'Can change user',4,'change_user'),(15,'Can delete user',4,'delete_user'),(16,'Can view user',4,'view_user'),(17,'Can add content type',5,'add_contenttype'),(18,'Can change content type',5,'change_contenttype'),(19,'Can delete content type',5,'delete_contenttype'),(20,'Can view content type',5,'view_contenttype'),(21,'Can add session',6,'add_session'),(22,'Can change session',6,'change_session'),(23,'Can delete session',6,'delete_session'),(24,'Can view session',6,'view_session'),(25,'Can add cliente',7,'add_cliente'),(26,'Can change cliente',7,'change_cliente'),(27,'Can delete cliente',7,'delete_cliente'),(28,'Can view cliente',7,'view_cliente'),(29,'Can add proveedor',8,'add_proveedor'),(30,'Can change proveedor',8,'change_proveedor'),(31,'Can delete proveedor',8,'delete_proveedor'),(32,'Can view proveedor',8,'view_proveedor'),(33,'Can add inventario',9,'add_inventario'),(34,'Can change inventario',9,'change_inventario'),(35,'Can delete inventario',9,'delete_inventario'),(36,'Can view inventario',9,'view_inventario'),(37,'Can add Nota de Proveedor',10,'add_historialproveedoresnotas'),(38,'Can change Nota de Proveedor',10,'change_historialproveedoresnotas'),(39,'Can delete Nota de Proveedor',10,'delete_historialproveedoresnotas'),(40,'Can view Nota de Proveedor',10,'view_historialproveedoresnotas'),(41,'Can add movimientos inventario',11,'add_movimientosinventario'),(42,'Can change movimientos inventario',11,'change_movimientosinventario'),(43,'Can delete movimientos inventario',11,'delete_movimientosinventario'),(44,'Can view movimientos inventario',11,'view_movimientosinventario');
/*!40000 ALTER TABLE `auth_permission` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping data for table `auth_user`
--

LOCK TABLES `auth_user` WRITE;
/*!40000 ALTER TABLE `auth_user` DISABLE KEYS */;
INSERT INTO `auth_user` VALUES (1,'pbkdf2_sha256$1000000$i8HfBBMezjLRi5G9zbeqYX$R8W7hyFfurosc7u1pcgs3e0RKOnK9KrqMZqlkcrXapE=',NULL,1,'inventario','','','anthonyatay1903@gmail.com',1,1,'2025-12-06 17:18:48.795132'),(2,'pbkdf2_sha256$1000000$RczUKlU1tfvgsdxXtu7k2y$3+1pOg3RVxOelwS1Nkjn6z3N7u6Dy5OYvOWVipr+ND4=','2025-12-08 20:36:50.472107',1,'inventario_test','','','anthonyatay1903@gmail.com',1,1,'2025-12-08 20:34:37.087727');
/*!40000 ALTER TABLE `auth_user` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping data for table `auth_user_groups`
--

LOCK TABLES `auth_user_groups` WRITE;
/*!40000 ALTER TABLE `auth_user_groups` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_user_groups` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping data for table `auth_user_user_permissions`
--

LOCK TABLES `auth_user_user_permissions` WRITE;
/*!40000 ALTER TABLE `auth_user_user_permissions` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_user_user_permissions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping data for table `django_admin_log`
--

LOCK TABLES `django_admin_log` WRITE;
/*!40000 ALTER TABLE `django_admin_log` DISABLE KEYS */;
INSERT INTO `django_admin_log` VALUES (1,'2025-12-08 20:38:17.332997','1','Cliente object (1)',1,'[{\"added\": {}}]',7,2),(2,'2025-12-08 20:44:29.473672','2','Cliente object (2)',1,'[{\"added\": {}}]',7,2),(3,'2025-12-09 00:33:02.708579','1','id: 1 - anthoni - 4564561515 - prueba - 1452-525 - puerto',1,'[{\"added\": {}}]',8,2),(4,'2025-12-09 11:33:25.160663','1','id: 1 - arroz - paquete 1 kg - 0 - 200 - 400 - 30 - 200',1,'[{\"added\": {}}]',9,2),(5,'2025-12-09 11:55:54.502377','2','id: 2 - espagueti - 1kg - 0 - 200 - 450 - 35 - 200',1,'[{\"added\": {}}]',9,2),(6,'2025-12-09 18:42:29.292526','1','HistorialProveedoresNotas object (1)',1,'[{\"added\": {}}]',10,2),(7,'2025-12-09 19:09:56.790471','1','alonso atay jr jr — 2025-12-09 — entrego todo completo con 15% de descuento',2,'[]',10,2),(8,'2025-12-10 00:29:10.978610','8','id: 8 - jugo de naranja - juste - 30 - 150.00 - 300.00 - 20 - 80',2,'[{\"changed\": {\"fields\": [\"Cantidad en Stock\"]}}]',9,2),(9,'2025-12-10 00:29:18.282652','7','id: 7 - bolsa de pan - bolsa de pan frases de 20 unidades - 30 - 300.00 - 500.00 - 50 - 250',2,'[{\"changed\": {\"fields\": [\"Cantidad en Stock\"]}}]',9,2),(10,'2025-12-10 00:29:25.940188','6','id: 6 - jabon - jabon de 150g para baño - 40 - 100.00 - 350.00 - 20 - 75',2,'[{\"changed\": {\"fields\": [\"Cantidad en Stock\"]}}]',9,2),(11,'2025-12-10 00:29:32.744001','4','id: 4 - coca cola - 1 litro - 120 - 200.00 - 450.00 - 40 - 200',2,'[{\"changed\": {\"fields\": [\"Cantidad en Stock\"]}}]',9,2),(12,'2025-12-10 00:29:40.756896','3','id: 3 - harina pan - 1 kg blanca - 100 - 175.00 - 350.00 - 100 - 300',2,'[{\"changed\": {\"fields\": [\"Cantidad en Stock\"]}}]',9,2),(13,'2025-12-10 00:29:47.652064','2','id: 2 - espagueti - 1kg - 50 - 200.00 - 450.00 - 35 - 200',2,'[{\"changed\": {\"fields\": [\"Cantidad en Stock\"]}}]',9,2),(14,'2025-12-10 00:29:53.916811','1','id: 1 - arroz - paquete 1 kg - prueba edit - 50 - 200.00 - 400.00 - 30 - 200',2,'[{\"changed\": {\"fields\": [\"Cantidad en Stock\"]}}]',9,2),(15,'2025-12-10 19:24:13.915814','1','id: 1 - arroz - paquete 1 kg - prueba edit - 50 - 200.00 - 400.00 - 30 - 200',2,'[{\"changed\": {\"fields\": [\"C\\u00f3digo del Producto\"]}}]',9,2),(16,'2025-12-10 19:29:38.956894','2','id: 2 - 000p-2 - espagueti - 1kg - 50 - 200.00 - 450.00 - 35 - 200',2,'[{\"changed\": {\"fields\": [\"C\\u00f3digo del Producto\"]}}]',9,2),(17,'2025-12-10 19:29:51.218285','3','id: 3 - 0000 b 3 - harina pan - 1 kg blanca - 100 - 175.00 - 350.00 - 100 - 300',2,'[{\"changed\": {\"fields\": [\"C\\u00f3digo del Producto\"]}}]',9,2),(18,'2025-12-10 19:57:20.366555','1','ENTRADA - arroz - 5 unidades el 2025-12-10',1,'[{\"added\": {}}]',11,2);
/*!40000 ALTER TABLE `django_admin_log` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping data for table `django_content_type`
--

LOCK TABLES `django_content_type` WRITE;
/*!40000 ALTER TABLE `django_content_type` DISABLE KEYS */;
INSERT INTO `django_content_type` VALUES (1,'admin','logentry'),(3,'auth','group'),(2,'auth','permission'),(4,'auth','user'),(5,'contenttypes','contenttype'),(7,'libreria','cliente'),(10,'libreria','historialproveedoresnotas'),(9,'libreria','inventario'),(11,'libreria','movimientosinventario'),(8,'libreria','proveedor'),(6,'sessions','session');
/*!40000 ALTER TABLE `django_content_type` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping data for table `django_migrations`
--

LOCK TABLES `django_migrations` WRITE;
/*!40000 ALTER TABLE `django_migrations` DISABLE KEYS */;
INSERT INTO `django_migrations` VALUES (1,'contenttypes','0001_initial','2025-12-06 17:14:05.595742'),(2,'auth','0001_initial','2025-12-06 17:14:09.045892'),(3,'admin','0001_initial','2025-12-06 17:14:09.873754'),(4,'admin','0002_logentry_remove_auto_add','2025-12-06 17:14:09.961797'),(5,'admin','0003_logentry_add_action_flag_choices','2025-12-06 17:14:10.039292'),(6,'contenttypes','0002_remove_content_type_name','2025-12-06 17:14:10.767836'),(7,'auth','0002_alter_permission_name_max_length','2025-12-06 17:14:11.193454'),(8,'auth','0003_alter_user_email_max_length','2025-12-06 17:14:11.417543'),(9,'auth','0004_alter_user_username_opts','2025-12-06 17:14:11.494871'),(10,'auth','0005_alter_user_last_login_null','2025-12-06 17:14:11.883992'),(11,'auth','0006_require_contenttypes_0002','2025-12-06 17:14:11.905786'),(12,'auth','0007_alter_validators_add_error_messages','2025-12-06 17:14:12.002139'),(13,'auth','0008_alter_user_username_max_length','2025-12-06 17:14:12.447639'),(14,'auth','0009_alter_user_last_name_max_length','2025-12-06 17:14:12.899527'),(15,'auth','0010_alter_group_name_max_length','2025-12-06 17:14:13.083848'),(16,'auth','0011_update_proxy_permissions','2025-12-06 17:14:13.147004'),(17,'auth','0012_alter_user_first_name_max_length','2025-12-06 17:14:13.625285'),(18,'sessions','0001_initial','2025-12-06 17:14:13.859831'),(19,'libreria','0001_initial','2025-12-08 20:08:43.795647'),(20,'libreria','0002_alter_cliente_cedula_alter_cliente_email_and_more','2025-12-08 20:20:12.238219'),(21,'libreria','0003_alter_cliente_cedula_alter_cliente_email_and_more','2025-12-08 21:54:34.011405'),(22,'libreria','0004_alter_cliente_cedula','2025-12-08 22:10:57.809064'),(23,'libreria','0005_proveedor','2025-12-09 00:30:01.903603'),(24,'libreria','0006_inventario','2025-12-09 02:03:27.118548'),(25,'libreria','0007_inventario_categoria','2025-12-09 11:30:57.870329'),(26,'libreria','0008_alter_cliente_cedula','2025-12-09 11:31:47.392821'),(27,'libreria','0009_historialproveedoresnotas','2025-12-09 18:26:42.856686'),(28,'libreria','0010_inventario_codigo_producto','2025-12-10 19:23:46.309416'),(29,'libreria','0011_movimientosinventario','2025-12-10 19:56:34.003679'),(30,'libreria','0012_alter_inventario_categoria','2025-12-11 01:27:46.368377');
/*!40000 ALTER TABLE `django_migrations` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping data for table `django_session`
--

LOCK TABLES `django_session` WRITE;
/*!40000 ALTER TABLE `django_session` DISABLE KEYS */;
INSERT INTO `django_session` VALUES ('3ic5u2kydm1dhnue0hij8hft0nenbp1m','.eJxVjDEOwyAQBP9CHSHfgdGRMn3egMDHBScRloxdWfl7bMlF0myxM7ubCnFdSlhbnsPI6qpQXX67FIdXrgfgZ6yPSQ9TXeYx6UPRJ236PnF-307376DEVvY1CCYRz8lk6i0jI7G14kkI0bBxtgcSASDuEgh5x4b34A68iU7U5wvutDfu:1vShyU:fvJ_B2xDTGae-95Loph1mSviCGmgj0D1ikZQj9b9DV8','2025-12-22 20:36:50.480805');
/*!40000 ALTER TABLE `django_session` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping data for table `libreria_cliente`
--

LOCK TABLES `libreria_cliente` WRITE;
/*!40000 ALTER TABLE `libreria_cliente` DISABLE KEYS */;
INSERT INTO `libreria_cliente` VALUES (7,'anthony atayyyy tercera','anthonyatay192303@gmail.com','0426202222',302051111,'barcelona-puerto'),(8,'alonso','starlord@gmail.com','+58 4249487329',36521285,'barcelona'),(9,'pruebaaaa','anthonyatay8@gmail.com','484856112',212125111,'puerto la cruz');
/*!40000 ALTER TABLE `libreria_cliente` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping data for table `libreria_historialproveedoresnotas`
--

LOCK TABLES `libreria_historialproveedoresnotas` WRITE;
/*!40000 ALTER TABLE `libreria_historialproveedoresnotas` DISABLE KEYS */;
INSERT INTO `libreria_historialproveedoresnotas` VALUES (1,'2025-12-09 18:42:29.290965','entrego todo completo con 15% de descuento prueba edit',3),(2,'2025-12-09 23:56:59.395880','pagar en 4 dias para 20%',2),(3,'2025-12-10 00:18:14.618913','prueba 3 luego de tener la tabla mejor',3),(4,'2025-12-11 18:58:32.080779','trajo los 100 paquetes de arroz de 1 kg pagadero en 3 dias 30%',4);
/*!40000 ALTER TABLE `libreria_historialproveedoresnotas` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping data for table `libreria_inventario`
--

LOCK TABLES `libreria_inventario` WRITE;
/*!40000 ALTER TABLE `libreria_inventario` DISABLE KEYS */;
INSERT INTO `libreria_inventario` VALUES (1,'arroz','paquete 1 kg - prueba edit',130,200.00,400.00,30,200,'ALIMENTACION','0001'),(2,'espagueti','1kg',50,200.00,450.00,35,200,'alimentación','000p-2'),(3,'harina pan','1 kg blanca',140,175.00,350.00,100,300,'alimentación','0000 b 3'),(4,'coca cola','1 litro',142,200.00,450.00,40,200,'BEBIDAS','00004 C 1'),(6,'jabon','jabon de 150g para baño',40,100.00,350.00,20,75,'HOGAR',NULL),(7,'bolsa de pan','bolsa de pan frases de 20 unidades',60,300.00,500.00,50,250,'alimentación','0003-P'),(8,'jugo de naranja','juste',30,150.00,300.00,20,80,'BEBIDAS',NULL),(9,'prueba','distribución de inventario',20,100.00,200.00,10,100,'OTRO','00005M'),(10,'cloro','envase de 1Litro 5%',95,100.25,200.50,55,250,'HOGAR','00008-12 Y');
/*!40000 ALTER TABLE `libreria_inventario` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping data for table `libreria_movimientosinventario`
--

LOCK TABLES `libreria_movimientosinventario` WRITE;
/*!40000 ALTER TABLE `libreria_movimientosinventario` DISABLE KEYS */;
INSERT INTO `libreria_movimientosinventario` VALUES (1,'ENTRADA',5,'2025-12-10 19:57:20.364972',1,2),(2,'ENTRADA',50,'2025-12-10 23:50:47.068176',3,3),(3,'ENTRADA',35,'2025-12-10 23:52:02.591351',7,2),(4,'SALIDA',50,'2025-12-10 23:52:33.238841',7,NULL),(6,'SALIDA',3,'2025-12-11 01:25:00.010211',4,NULL),(7,'SALIDA',5,'2025-12-11 01:25:43.719043',4,NULL),(8,'ENTRADA',30,'2025-12-11 18:07:46.843763',4,2),(9,'SALIDA',10,'2025-12-11 18:12:26.014749',3,NULL),(10,'ENTRADA',50,'2025-12-11 18:12:40.944224',7,2),(11,'ENTRADA',100,'2025-12-11 18:57:41.490892',1,4),(12,'SALIDA',20,'2025-12-11 19:02:30.656296',1,NULL);
/*!40000 ALTER TABLE `libreria_movimientosinventario` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping data for table `libreria_proveedor`
--

LOCK TABLES `libreria_proveedor` WRITE;
/*!40000 ALTER TABLE `libreria_proveedor` DISABLE KEYS */;
INSERT INTO `libreria_proveedor` VALUES (2,'alonso atay','4548944125-112','vendedorrrr','1-8840930','barcelona-puerto editar'),(3,'juan','0426202538645','prueba buscador','1-34412304','barcelona'),(4,'fulano de tal','04152866478','prueba','11352874-5','puerto la cruz');
/*!40000 ALTER TABLE `libreria_proveedor` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-12-11 15:22:22
