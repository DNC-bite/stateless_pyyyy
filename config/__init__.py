# Si mysqlclient no está instalado (suele fallar en Windows), usamos PyMySQL como respaldo.
try:
    import MySQLdb  # noqa: F401
except ImportError:
    try:
        import pymysql

        pymysql.version_info = (2, 2, 1, "final", 0)  # Django exige mysqlclient >= 2.2.1
        pymysql.install_as_MySQLdb()
    except ImportError:
        pass
