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
-- Table structure for table `auth_group`
--

DROP TABLE IF EXISTS `auth_group`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_group` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(150) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_group`
--

LOCK TABLES `auth_group` WRITE;
/*!40000 ALTER TABLE `auth_group` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_group` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_group_permissions`
--

DROP TABLE IF EXISTS `auth_group_permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_group_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `group_id` int NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_group_permissions_group_id_permission_id_0cd325b0_uniq` (`group_id`,`permission_id`),
  KEY `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `auth_group_permissions_group_id_b120cbf9_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_group_permissions`
--

LOCK TABLES `auth_group_permissions` WRITE;
/*!40000 ALTER TABLE `auth_group_permissions` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_group_permissions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_permission`
--

DROP TABLE IF EXISTS `auth_permission`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_permission` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `content_type_id` int NOT NULL,
  `codename` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_permission_content_type_id_codename_01ab375a_uniq` (`content_type_id`,`codename`),
  CONSTRAINT `auth_permission_content_type_id_2f476e4b_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=49 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_permission`
--

LOCK TABLES `auth_permission` WRITE;
/*!40000 ALTER TABLE `auth_permission` DISABLE KEYS */;
INSERT INTO `auth_permission` VALUES (1,'Can add log entry',1,'add_logentry'),(2,'Can change log entry',1,'change_logentry'),(3,'Can delete log entry',1,'delete_logentry'),(4,'Can view log entry',1,'view_logentry'),(5,'Can add permission',2,'add_permission'),(6,'Can change permission',2,'change_permission'),(7,'Can delete permission',2,'delete_permission'),(8,'Can view permission',2,'view_permission'),(9,'Can add group',3,'add_group'),(10,'Can change group',3,'change_group'),(11,'Can delete group',3,'delete_group'),(12,'Can view group',3,'view_group'),(13,'Can add user',4,'add_user'),(14,'Can change user',4,'change_user'),(15,'Can delete user',4,'delete_user'),(16,'Can view user',4,'view_user'),(17,'Can add content type',5,'add_contenttype'),(18,'Can change content type',5,'change_contenttype'),(19,'Can delete content type',5,'delete_contenttype'),(20,'Can view content type',5,'view_contenttype'),(21,'Can add session',6,'add_session'),(22,'Can change session',6,'change_session'),(23,'Can delete session',6,'delete_session'),(24,'Can view session',6,'view_session'),(25,'Can add cliente',7,'add_cliente'),(26,'Can change cliente',7,'change_cliente'),(27,'Can delete cliente',7,'delete_cliente'),(28,'Can view cliente',7,'view_cliente'),(29,'Can add proveedor',8,'add_proveedor'),(30,'Can change proveedor',8,'change_proveedor'),(31,'Can delete proveedor',8,'delete_proveedor'),(32,'Can view proveedor',8,'view_proveedor'),(33,'Can add inventario',9,'add_inventario'),(34,'Can change inventario',9,'change_inventario'),(35,'Can delete inventario',9,'delete_inventario'),(36,'Can view inventario',9,'view_inventario'),(37,'Can add Nota de Proveedor',10,'add_historialproveedoresnotas'),(38,'Can change Nota de Proveedor',10,'change_historialproveedoresnotas'),(39,'Can delete Nota de Proveedor',10,'delete_historialproveedoresnotas'),(40,'Can view Nota de Proveedor',10,'view_historialproveedoresnotas'),(41,'Can add movimientos inventario',11,'add_movimientosinventario'),(42,'Can change movimientos inventario',11,'change_movimientosinventario'),(43,'Can delete movimientos inventario',11,'delete_movimientosinventario'),(44,'Can view movimientos inventario',11,'view_movimientosinventario'),(45,'Can add Perfil de Usuario',12,'add_perfilusuario'),(46,'Can change Perfil de Usuario',12,'change_perfilusuario'),(47,'Can delete Perfil de Usuario',12,'delete_perfilusuario'),(48,'Can view Perfil de Usuario',12,'view_perfilusuario');
/*!40000 ALTER TABLE `auth_permission` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_user`
--

DROP TABLE IF EXISTS `auth_user`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_user` (
  `id` int NOT NULL AUTO_INCREMENT,
  `password` varchar(128) NOT NULL,
  `last_login` datetime(6) DEFAULT NULL,
  `is_superuser` tinyint(1) NOT NULL,
  `username` varchar(150) NOT NULL,
  `first_name` varchar(150) NOT NULL,
  `last_name` varchar(150) NOT NULL,
  `email` varchar(254) NOT NULL,
  `is_staff` tinyint(1) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `date_joined` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_user`
--

LOCK TABLES `auth_user` WRITE;
/*!40000 ALTER TABLE `auth_user` DISABLE KEYS */;
INSERT INTO `auth_user` VALUES (1,'pbkdf2_sha256$1000000$i8HfBBMezjLRi5G9zbeqYX$R8W7hyFfurosc7u1pcgs3e0RKOnK9KrqMZqlkcrXapE=',NULL,1,'inventario','','','anthonyatay1903@gmail.com',1,1,'2025-12-06 17:18:48.795132'),(2,'pbkdf2_sha256$1000000$RczUKlU1tfvgsdxXtu7k2y$3+1pOg3RVxOelwS1Nkjn6z3N7u6Dy5OYvOWVipr+ND4=','2026-01-11 01:10:05.283323',1,'inventario_test','Anthony','mestre','anthonyatay1903@gmail.com',1,1,'2025-12-08 20:34:37.087727'),(5,'pbkdf2_sha256$1000000$DzZDrNIaVmiKg4HXEI22kM$ZtB4IpwbPjirxUlvPtntAADlcwkRA9iYfsHLhqmYy2A=','2026-01-11 01:04:48.328886',0,'inventario_rol_test','test','test','test@gmail.com',0,1,'2026-01-11 01:02:25.121023');
/*!40000 ALTER TABLE `auth_user` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_user_groups`
--

DROP TABLE IF EXISTS `auth_user_groups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_user_groups` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `group_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_user_groups_user_id_group_id_94350c0c_uniq` (`user_id`,`group_id`),
  KEY `auth_user_groups_group_id_97559544_fk_auth_group_id` (`group_id`),
  CONSTRAINT `auth_user_groups_group_id_97559544_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`),
  CONSTRAINT `auth_user_groups_user_id_6a12ed8b_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_user_groups`
--

LOCK TABLES `auth_user_groups` WRITE;
/*!40000 ALTER TABLE `auth_user_groups` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_user_groups` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_user_user_permissions`
--

DROP TABLE IF EXISTS `auth_user_user_permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_user_user_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_user_user_permissions_user_id_permission_id_14a6b632_uniq` (`user_id`,`permission_id`),
  KEY `auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_user_user_permissions`
--

LOCK TABLES `auth_user_user_permissions` WRITE;
/*!40000 ALTER TABLE `auth_user_user_permissions` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_user_user_permissions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_admin_log`
--

DROP TABLE IF EXISTS `django_admin_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_admin_log` (
  `id` int NOT NULL AUTO_INCREMENT,
  `action_time` datetime(6) NOT NULL,
  `object_id` longtext,
  `object_repr` varchar(200) NOT NULL,
  `action_flag` smallint unsigned NOT NULL,
  `change_message` longtext NOT NULL,
  `content_type_id` int DEFAULT NULL,
  `user_id` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `django_admin_log_content_type_id_c4bce8eb_fk_django_co` (`content_type_id`),
  KEY `django_admin_log_user_id_c564eba6_fk_auth_user_id` (`user_id`),
  CONSTRAINT `django_admin_log_content_type_id_c4bce8eb_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`),
  CONSTRAINT `django_admin_log_user_id_c564eba6_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `django_admin_log_chk_1` CHECK ((`action_flag` >= 0))
) ENGINE=InnoDB AUTO_INCREMENT=23 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_admin_log`
--

LOCK TABLES `django_admin_log` WRITE;
/*!40000 ALTER TABLE `django_admin_log` DISABLE KEYS */;
INSERT INTO `django_admin_log` VALUES (1,'2025-12-08 20:38:17.332997','1','Cliente object (1)',1,'[{\"added\": {}}]',7,2),(2,'2025-12-08 20:44:29.473672','2','Cliente object (2)',1,'[{\"added\": {}}]',7,2),(3,'2025-12-09 00:33:02.708579','1','id: 1 - anthoni - 4564561515 - prueba - 1452-525 - puerto',1,'[{\"added\": {}}]',8,2),(4,'2025-12-09 11:33:25.160663','1','id: 1 - arroz - paquete 1 kg - 0 - 200 - 400 - 30 - 200',1,'[{\"added\": {}}]',9,2),(5,'2025-12-09 11:55:54.502377','2','id: 2 - espagueti - 1kg - 0 - 200 - 450 - 35 - 200',1,'[{\"added\": {}}]',9,2),(6,'2025-12-09 18:42:29.292526','1','HistorialProveedoresNotas object (1)',1,'[{\"added\": {}}]',10,2),(7,'2025-12-09 19:09:56.790471','1','alonso atay jr jr — 2025-12-09 — entrego todo completo con 15% de descuento',2,'[]',10,2),(8,'2025-12-10 00:29:10.978610','8','id: 8 - jugo de naranja - juste - 30 - 150.00 - 300.00 - 20 - 80',2,'[{\"changed\": {\"fields\": [\"Cantidad en Stock\"]}}]',9,2),(9,'2025-12-10 00:29:18.282652','7','id: 7 - bolsa de pan - bolsa de pan frases de 20 unidades - 30 - 300.00 - 500.00 - 50 - 250',2,'[{\"changed\": {\"fields\": [\"Cantidad en Stock\"]}}]',9,2),(10,'2025-12-10 00:29:25.940188','6','id: 6 - jabon - jabon de 150g para baño - 40 - 100.00 - 350.00 - 20 - 75',2,'[{\"changed\": {\"fields\": [\"Cantidad en Stock\"]}}]',9,2),(11,'2025-12-10 00:29:32.744001','4','id: 4 - coca cola - 1 litro - 120 - 200.00 - 450.00 - 40 - 200',2,'[{\"changed\": {\"fields\": [\"Cantidad en Stock\"]}}]',9,2),(12,'2025-12-10 00:29:40.756896','3','id: 3 - harina pan - 1 kg blanca - 100 - 175.00 - 350.00 - 100 - 300',2,'[{\"changed\": {\"fields\": [\"Cantidad en Stock\"]}}]',9,2),(13,'2025-12-10 00:29:47.652064','2','id: 2 - espagueti - 1kg - 50 - 200.00 - 450.00 - 35 - 200',2,'[{\"changed\": {\"fields\": [\"Cantidad en Stock\"]}}]',9,2),(14,'2025-12-10 00:29:53.916811','1','id: 1 - arroz - paquete 1 kg - prueba edit - 50 - 200.00 - 400.00 - 30 - 200',2,'[{\"changed\": {\"fields\": [\"Cantidad en Stock\"]}}]',9,2),(15,'2025-12-10 19:24:13.915814','1','id: 1 - arroz - paquete 1 kg - prueba edit - 50 - 200.00 - 400.00 - 30 - 200',2,'[{\"changed\": {\"fields\": [\"C\\u00f3digo del Producto\"]}}]',9,2),(16,'2025-12-10 19:29:38.956894','2','id: 2 - 000p-2 - espagueti - 1kg - 50 - 200.00 - 450.00 - 35 - 200',2,'[{\"changed\": {\"fields\": [\"C\\u00f3digo del Producto\"]}}]',9,2),(17,'2025-12-10 19:29:51.218285','3','id: 3 - 0000 b 3 - harina pan - 1 kg blanca - 100 - 175.00 - 350.00 - 100 - 300',2,'[{\"changed\": {\"fields\": [\"C\\u00f3digo del Producto\"]}}]',9,2),(18,'2025-12-10 19:57:20.366555','1','ENTRADA - arroz - 5 unidades el 2025-12-10',1,'[{\"added\": {}}]',11,2),(19,'2026-01-06 01:26:55.499000','3','anthony_test',1,'[{\"added\": {}}, {\"added\": {\"name\": \"Perfil de Usuario\", \"object\": \"Perfil de anthony_test\"}}]',4,2),(20,'2026-01-06 15:51:51.922166','3','Perfil de inventario_test',2,'[{\"changed\": {\"fields\": [\"C\\u00e9dula\", \"Rol\", \"Tel\\u00e9fono\", \"Direcci\\u00f3n\"]}}]',12,2),(21,'2026-01-06 15:51:58.073803','2','Perfil de P_user',2,'[{\"changed\": {\"fields\": [\"Rol\"]}}]',12,2),(22,'2026-01-06 15:52:07.713978','1','Perfil de anthony_test',2,'[{\"changed\": {\"fields\": [\"C\\u00e9dula\"]}}]',12,2);
/*!40000 ALTER TABLE `django_admin_log` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_content_type`
--

DROP TABLE IF EXISTS `django_content_type`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_content_type` (
  `id` int NOT NULL AUTO_INCREMENT,
  `app_label` varchar(100) NOT NULL,
  `model` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `django_content_type_app_label_model_76bd3d3b_uniq` (`app_label`,`model`)
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_content_type`
--

LOCK TABLES `django_content_type` WRITE;
/*!40000 ALTER TABLE `django_content_type` DISABLE KEYS */;
INSERT INTO `django_content_type` VALUES (1,'admin','logentry'),(3,'auth','group'),(2,'auth','permission'),(4,'auth','user'),(5,'contenttypes','contenttype'),(7,'libreria','cliente'),(10,'libreria','historialproveedoresnotas'),(9,'libreria','inventario'),(11,'libreria','movimientosinventario'),(12,'libreria','perfilusuario'),(8,'libreria','proveedor'),(6,'sessions','session');
/*!40000 ALTER TABLE `django_content_type` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_migrations`
--

DROP TABLE IF EXISTS `django_migrations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_migrations` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `app` varchar(255) NOT NULL,
  `name` varchar(255) NOT NULL,
  `applied` datetime(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=38 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_migrations`
--

LOCK TABLES `django_migrations` WRITE;
/*!40000 ALTER TABLE `django_migrations` DISABLE KEYS */;
INSERT INTO `django_migrations` VALUES (1,'contenttypes','0001_initial','2025-12-06 17:14:05.595742'),(2,'auth','0001_initial','2025-12-06 17:14:09.045892'),(3,'admin','0001_initial','2025-12-06 17:14:09.873754'),(4,'admin','0002_logentry_remove_auto_add','2025-12-06 17:14:09.961797'),(5,'admin','0003_logentry_add_action_flag_choices','2025-12-06 17:14:10.039292'),(6,'contenttypes','0002_remove_content_type_name','2025-12-06 17:14:10.767836'),(7,'auth','0002_alter_permission_name_max_length','2025-12-06 17:14:11.193454'),(8,'auth','0003_alter_user_email_max_length','2025-12-06 17:14:11.417543'),(9,'auth','0004_alter_user_username_opts','2025-12-06 17:14:11.494871'),(10,'auth','0005_alter_user_last_login_null','2025-12-06 17:14:11.883992'),(11,'auth','0006_require_contenttypes_0002','2025-12-06 17:14:11.905786'),(12,'auth','0007_alter_validators_add_error_messages','2025-12-06 17:14:12.002139'),(13,'auth','0008_alter_user_username_max_length','2025-12-06 17:14:12.447639'),(14,'auth','0009_alter_user_last_name_max_length','2025-12-06 17:14:12.899527'),(15,'auth','0010_alter_group_name_max_length','2025-12-06 17:14:13.083848'),(16,'auth','0011_update_proxy_permissions','2025-12-06 17:14:13.147004'),(17,'auth','0012_alter_user_first_name_max_length','2025-12-06 17:14:13.625285'),(18,'sessions','0001_initial','2025-12-06 17:14:13.859831'),(19,'libreria','0001_initial','2025-12-08 20:08:43.795647'),(20,'libreria','0002_alter_cliente_cedula_alter_cliente_email_and_more','2025-12-08 20:20:12.238219'),(21,'libreria','0003_alter_cliente_cedula_alter_cliente_email_and_more','2025-12-08 21:54:34.011405'),(22,'libreria','0004_alter_cliente_cedula','2025-12-08 22:10:57.809064'),(23,'libreria','0005_proveedor','2025-12-09 00:30:01.903603'),(24,'libreria','0006_inventario','2025-12-09 02:03:27.118548'),(25,'libreria','0007_inventario_categoria','2025-12-09 11:30:57.870329'),(26,'libreria','0008_alter_cliente_cedula','2025-12-09 11:31:47.392821'),(27,'libreria','0009_historialproveedoresnotas','2025-12-09 18:26:42.856686'),(28,'libreria','0010_inventario_codigo_producto','2025-12-10 19:23:46.309416'),(29,'libreria','0011_movimientosinventario','2025-12-10 19:56:34.003679'),(30,'libreria','0012_alter_inventario_categoria','2025-12-11 01:27:46.368377'),(31,'libreria','0013_proveedor_dias_descuentos','2025-12-14 22:13:45.155475'),(32,'libreria','0014_perfilusuario','2026-01-06 01:17:34.193317'),(33,'libreria','0015_perfilusuario_cedula','2026-01-06 15:24:19.562202'),(34,'libreria','0016_perfilusuario_rol','2026-01-06 15:33:45.483111'),(35,'libreria','0017_remove_inventario_precio_venta_and_more','2026-01-09 14:28:45.706625'),(36,'libreria','0018_remove_perfilusuario_foto','2026-01-10 14:36:20.972499'),(37,'libreria','0019_alter_perfilusuario_rol','2026-01-11 00:42:00.869046');
/*!40000 ALTER TABLE `django_migrations` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_session`
--

DROP TABLE IF EXISTS `django_session`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_session` (
  `session_key` varchar(40) NOT NULL,
  `session_data` longtext NOT NULL,
  `expire_date` datetime(6) NOT NULL,
  PRIMARY KEY (`session_key`),
  KEY `django_session_expire_date_a5c62663` (`expire_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_session`
--

LOCK TABLES `django_session` WRITE;
/*!40000 ALTER TABLE `django_session` DISABLE KEYS */;
INSERT INTO `django_session` VALUES ('3ic5u2kydm1dhnue0hij8hft0nenbp1m','.eJxVjDEOwyAQBP9CHSHfgdGRMn3egMDHBScRloxdWfl7bMlF0myxM7ubCnFdSlhbnsPI6qpQXX67FIdXrgfgZ6yPSQ9TXeYx6UPRJ236PnF-307376DEVvY1CCYRz8lk6i0jI7G14kkI0bBxtgcSASDuEgh5x4b34A68iU7U5wvutDfu:1vShyU:fvJ_B2xDTGae-95Loph1mSviCGmgj0D1ikZQj9b9DV8','2025-12-22 20:36:50.480805'),('4kexh8wxox7djfd3urrfvgvghkh4030n','e30:1vd9EO:loBOgDKIaS8QPza1H9NQLKUWOC5I1F1WeV_fBUnFJSA','2026-01-20 15:44:24.881539'),('6kei98j7qvj3mayyvp0n524ss6ah9f46','e30:1vd9A3:gUGKrPt38l4IxHUmPeRqTxY06FKZ99pe_kSECKSgSa0','2026-01-20 15:39:55.550635'),('6lqr0x57s2zg5ijivoworheejxuoj0pj','.eJxVjDEOwyAQBP9CHSHfgdGRMn3egMDHBScRloxdWfl7bMlF0myxM7ubCnFdSlhbnsPI6qpQXX67FIdXrgfgZ6yPSQ9TXeYx6UPRJ236PnF-307376DEVvY1CCYRz8lk6i0jI7G14kkI0bBxtgcSASDuEgh5x4b34A68iU7U5wvutDfu:1vejy1:f_3R8JS5MJEqMRdD7ViOlx0Sp4OHrZxo1IFpe8Cb_Lk','2026-01-25 01:10:05.285239'),('adbuxxos154a8q0nfkac7cc0c3gf6ujy','.eJxVjDEOwyAQBP9CHSHfgdGRMn3egMDHBScRloxdWfl7bMlF0myxM7ubCnFdSlhbnsPI6qpQXX67FIdXrgfgZ6yPSQ9TXeYx6UPRJ236PnF-307376DEVvY1CCYRz8lk6i0jI7G14kkI0bBxtgcSASDuEgh5x4b34A68iU7U5wvutDfu:1vd9PW:xiLVHRmengDs73Gkm6jcxkVuMk4HiKVdTnZxRTlHKF8','2026-01-20 15:55:54.265110'),('brg27g98qccwzb0y1tgbp6er4i65njn0','e30:1vd953:vY1hwRrlHkhmu80xWWn2zuWl9yB9_FuCVmXIh5dvCf4','2026-01-20 15:34:45.473855'),('gi6ct6q134jx3mrdz3lp63is4n0l157s','e30:1vd95f:PpAoo_7MeQGW-Up2Vkw0giCtJXw9g6ZzMicYiWDJXfY','2026-01-20 15:35:23.081916'),('mtq9wpqqudqnelkxjnjazmi0tqgqfucl','.eJxVjDEOwyAQBP9CHSHfgdGRMn3egMDHBScRloxdWfl7bMlF0myxM7ubCnFdSlhbnsPI6qpQXX67FIdXrgfgZ6yPSQ9TXeYx6UPRJ236PnF-307376DEVvY1CCYRz8lk6i0jI7G14kkI0bBxtgcSASDuEgh5x4b34A68iU7U5wvutDfu:1veaWj:vkjZKdqqEbiRD_XhSi0HHPYw4D7G0uKki_uf9TAElEU','2026-01-24 15:05:17.287448'),('y9eu1ly0wqcnq1froizgh34takn2cqid','e30:1vd96C:Nm-V-yIPfayX1_AdHU0mpIDcT4oKlrHm9uMJzMP1vI8','2026-01-20 15:35:56.377207');
/*!40000 ALTER TABLE `django_session` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `libreria_cliente`
--

DROP TABLE IF EXISTS `libreria_cliente`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `libreria_cliente` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nombre` varchar(100) NOT NULL,
  `email` varchar(254) NOT NULL,
  `telefono` varchar(15) NOT NULL,
  `cedula` int NOT NULL,
  `direccion` longtext NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`),
  UNIQUE KEY `cedula` (`cedula`)
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `libreria_cliente`
--

LOCK TABLES `libreria_cliente` WRITE;
/*!40000 ALTER TABLE `libreria_cliente` DISABLE KEYS */;
INSERT INTO `libreria_cliente` VALUES (7,'anthony atayyyy tercera','anthonyatay192303@gmail.com','0426202222',302051111,'barcelona-puerto'),(8,'alonso','starlord@gmail.com','+58 4249487329',36521285,'barcelona'),(9,'pruebaaaa','anthonyatay8@gmail.com','484856112',212125111,'puerto la cruz');
/*!40000 ALTER TABLE `libreria_cliente` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `libreria_historialproveedoresnotas`
--

DROP TABLE IF EXISTS `libreria_historialproveedoresnotas`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `libreria_historialproveedoresnotas` (
  `id_historialproveedor` int NOT NULL AUTO_INCREMENT,
  `fecha_registro` datetime(6) NOT NULL,
  `detalle_nota` longtext NOT NULL,
  `proveedores_id` int NOT NULL,
  PRIMARY KEY (`id_historialproveedor`),
  KEY `libreria_historialpr_proveedores_id_3378d6fe_fk_libreria_` (`proveedores_id`),
  CONSTRAINT `libreria_historialpr_proveedores_id_3378d6fe_fk_libreria_` FOREIGN KEY (`proveedores_id`) REFERENCES `libreria_proveedor` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `libreria_historialproveedoresnotas`
--

LOCK TABLES `libreria_historialproveedoresnotas` WRITE;
/*!40000 ALTER TABLE `libreria_historialproveedoresnotas` DISABLE KEYS */;
/*!40000 ALTER TABLE `libreria_historialproveedoresnotas` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `libreria_inventario`
--

DROP TABLE IF EXISTS `libreria_inventario`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `libreria_inventario` (
  `id_producto` int NOT NULL AUTO_INCREMENT,
  `nombre_producto` varchar(100) NOT NULL,
  `descripcion` longtext NOT NULL,
  `cantidad` int NOT NULL,
  `costo_actual` decimal(10,2) NOT NULL,
  `stock_minimo` int NOT NULL,
  `stock_maximo` int NOT NULL,
  `categoria` varchar(20) NOT NULL,
  `codigo_producto` varchar(20) DEFAULT NULL,
  `cantidad_por_empaque` int NOT NULL,
  `costo_anterior` decimal(10,2) DEFAULT NULL,
  `unidad_empaque` varchar(20) NOT NULL,
  PRIMARY KEY (`id_producto`),
  UNIQUE KEY `codigo_producto` (`codigo_producto`)
) ENGINE=InnoDB AUTO_INCREMENT=70 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `libreria_inventario`
--

LOCK TABLES `libreria_inventario` WRITE;
/*!40000 ALTER TABLE `libreria_inventario` DISABLE KEYS */;
/*!40000 ALTER TABLE `libreria_inventario` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `libreria_movimientosinventario`
--

DROP TABLE IF EXISTS `libreria_movimientosinventario`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `libreria_movimientosinventario` (
  `id_movimiento` int NOT NULL AUTO_INCREMENT,
  `tipo_movimiento` varchar(10) NOT NULL,
  `cantidad` int NOT NULL,
  `fecha_movimiento` datetime(6) NOT NULL,
  `producto_id` int NOT NULL,
  `proveedor_id` int DEFAULT NULL,
  PRIMARY KEY (`id_movimiento`),
  KEY `libreria_movimientos_producto_id_76356a19_fk_libreria_` (`producto_id`),
  KEY `libreria_movimientos_proveedor_id_177df8e7_fk_libreria_` (`proveedor_id`),
  CONSTRAINT `libreria_movimientos_producto_id_76356a19_fk_libreria_` FOREIGN KEY (`producto_id`) REFERENCES `libreria_inventario` (`id_producto`),
  CONSTRAINT `libreria_movimientos_proveedor_id_177df8e7_fk_libreria_` FOREIGN KEY (`proveedor_id`) REFERENCES `libreria_proveedor` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `libreria_movimientosinventario`
--

LOCK TABLES `libreria_movimientosinventario` WRITE;
/*!40000 ALTER TABLE `libreria_movimientosinventario` DISABLE KEYS */;
/*!40000 ALTER TABLE `libreria_movimientosinventario` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `libreria_perfilusuario`
--

DROP TABLE IF EXISTS `libreria_perfilusuario`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `libreria_perfilusuario` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `telefono` varchar(20) NOT NULL,
  `direccion` longtext NOT NULL,
  `user_id` int NOT NULL,
  `cedula` varchar(20) DEFAULT NULL,
  `rol` varchar(20) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`),
  UNIQUE KEY `cedula` (`cedula`),
  CONSTRAINT `libreria_perfilusuario_user_id_0a8a7410_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `libreria_perfilusuario`
--

LOCK TABLES `libreria_perfilusuario` WRITE;
/*!40000 ALTER TABLE `libreria_perfilusuario` DISABLE KEYS */;
INSERT INTO `libreria_perfilusuario` VALUES (3,'5454564584','prueba',2,'302056','admin'),(4,'0426202538645','prueba',5,'205683','inventario');
/*!40000 ALTER TABLE `libreria_perfilusuario` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `libreria_proveedor`
--

DROP TABLE IF EXISTS `libreria_proveedor`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `libreria_proveedor` (
  `id` int NOT NULL AUTO_INCREMENT,
  `nombre` varchar(100) NOT NULL,
  `telefono` varchar(15) NOT NULL,
  `razonsocial` varchar(150) NOT NULL,
  `rif` varchar(20) NOT NULL,
  `direccion` longtext NOT NULL,
  `dias_descuentos` varchar(150) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `rif` (`rif`)
) ENGINE=InnoDB AUTO_INCREMENT=105 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `libreria_proveedor`
--

LOCK TABLES `libreria_proveedor` WRITE;
/*!40000 ALTER TABLE `libreria_proveedor` DISABLE KEYS */;
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

-- Dump completed on 2026-01-10 21:29:09
