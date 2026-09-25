# Despliegue de GrapeSense en Render

Esta guía publica una sola instalación multiempresa compuesta por:

- un servicio web Docker con React y FastAPI;
- una base PostgreSQL administrada;
- un disco persistente para los modelos entrenados por bodega.

La infraestructura se describe en `render.yaml`. No se deben copiar contraseñas ni URLs privadas dentro del repositorio.

## 1. Publicar el código en GitHub

Confirmar que los cambios estén guardados en la rama que se desplegará y subirlos al repositorio privado. Render volverá a desplegar GrapeSense automáticamente cuando esa rama reciba cambios.

Antes de subir, revisar:

```bash
git status
git diff --check
```

Los archivos `.env`, el secreto local, los modelos generados y la carpeta `venv` están excluidos de Git.

## 2. Crear el Blueprint

1. Ingresar a <https://dashboard.render.com/>.
2. Seleccionar **New → Blueprint**.
3. Conectar el repositorio privado de GrapeSense.
4. Elegir el archivo `render.yaml` de la raíz.
5. Revisar los dos recursos que se crearán:
   - `grapesense`, servicio web;
   - `grapesense-db`, PostgreSQL.
6. Confirmar la creación.

El primer despliegue construye React, instala Python, inicia FastAPI y ejecuta las migraciones al consultar la aplicación. El servicio queda disponible en una dirección similar a `https://grapesense.onrender.com`.

## 3. Verificar el despliegue

Comprobar estas direcciones:

```text
https://<servicio>.onrender.com/api/health
https://<servicio>.onrender.com/
```

La verificación de salud debe responder con base conectada y modelo disponible. Si la base está vacía, la página mostrará la configuración de la primera organización.

## 4. Crear una instalación nueva o migrar la local

### Alternativa A: instalación nueva

Abrir la aplicación y completar el asistente inicial. Esta opción crea una plataforma vacía y luego permite importar muestras desde la interfaz.

### Alternativa B: conservar la base local

Crear primero un respaldo local mediante el script incluido:

```bash
./scripts/respaldo_postgresql.sh
```

El archivo y su suma de comprobación se guardan en `backups/render/`, con permisos privados y fuera de Git.

La base de `render.yaml` sólo acepta conexiones desde la red privada de Render. Para restaurar desde la computadora:

1. abrir `grapesense-db` en Render;
2. habilitar temporalmente la IP pública de la computadora en **Network / Inbound IP Rules**;
3. copiar la URL externa de PostgreSQL sin guardarla en ningún archivo;
4. restaurar el respaldo en la base vacía:

```bash
pg_restore --no-owner --no-acl --dbname="URL_EXTERNA_DE_RENDER" backups/render/tesis_uva_FECHA.dump
```

Después de comprobar los datos, eliminar nuevamente la regla pública. La aplicación utiliza internamente `DATABASE_URL`, suministrada de forma automática por Render.

## 5. Modelos existentes

El modelo base forma parte de la imagen y siempre está disponible. Los modelos nuevos se escriben en `/var/data/models`, que corresponde al disco persistente.

El candidato local anterior no se copia automáticamente porque pertenece a la computadora de desarrollo y no está activo. Se puede volver a entrenar desde la plataforma una vez migradas las muestras; el nuevo candidato quedará almacenado de forma persistente en Render.

## 6. Dominio propio

Cuando la dirección `onrender.com` funcione:

1. abrir el servicio `grapesense`;
2. ingresar en **Settings → Custom Domains**;
3. agregar, por ejemplo, `app.grapesense.com.ar`;
4. copiar en el proveedor del dominio los registros DNS indicados por Render;
5. esperar la verificación y el certificado HTTPS automático.

## 7. Copias de seguridad y operación

- Usar un plan PostgreSQL pago; la base gratuita vence y no es apropiada para clientes.
- Revisar periódicamente las copias y la restauración.
- No eliminar el disco `grapesense-models`: contiene los modelos entrenados por bodega.
- Revisar los registros de Render cuando falle una consulta climática o un entrenamiento.
- Probar los roles de cada bodega después de cada cambio relevante.
- Mantener la aplicación y PostgreSQL en la misma región.

## 8. Actualizaciones

Una actualización normal consiste en subir cambios a la rama conectada. Render construye una imagen nueva y conserva PostgreSQL y el disco de modelos.

Antes de publicar una actualización:

```bash
python -m py_compile modelo_final/backend/api.py modelo_final/backend/core/*.py modelo_final/backend/ml/*.py modelo_final/backend/services/*.py
cd modelo_final/frontend && npm ci && npm run build
```

No utilizar el archivo `iniciar.sh` en Render: está pensado exclusivamente para ejecutar GrapeSense en la computadora local.
