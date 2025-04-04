# Integración PedidosYa Envíos para Odoo 18

Este módulo integra los servicios de entrega de PedidosYa Courier API con Odoo 18, permitiendo a los usuarios crear envíos, calcular costos de envío, realizar seguimiento y obtener actualizaciones de estado en tiempo real.

## Características

- **Cálculo de costos de envío:** Obtén cotizaciones de precios en tiempo real.
- **Creación de envíos:** Genera envíos expresos (lo antes posible) o programados.
- **Seguimiento de paquetes:** Visualiza el estado actual de los envíos.
- **Verificación de cobertura:** Comprueba si PedidosYa puede realizar el envío entre dos direcciones.
- **Etiquetas de envío:** Genera etiquetas PDF para tus envíos.
- **Notificaciones en tiempo real:** Recibe actualizaciones de estado automáticas mediante webhooks.

## Requisitos

- Odoo 18
- Módulos base: delivery, stock, sale
- Credenciales de API de PedidosYa (API Key y API Secret)
- URL accesible desde internet para webhooks (opcional, pero recomendado)

## Instalación

1. Copia el módulo en el directorio de addons de Odoo
2. Actualiza la lista de aplicaciones
3. Instala el módulo "PedidosYa Shipping Integration"

## Configuración

### 1. Obtener credenciales API de PedidosYa

Contacta a tu representante de cuenta de PedidosYa para solicitar una API Key y API Secret. Especifica si necesitas acceso al entorno de pruebas o producción.

### 2. Configurar método de envío

1. Ve a Inventario → Configuración → Métodos de entrega
2. Crea un nuevo método de entrega o edita uno existente
3. Selecciona "PedidosYa" como proveedor
4. Configura:
  - API Key y API Secret
  - Entorno (pruebas o producción)
  - Tipo de servicio (Express o Programado)

### 3. Configurar webhooks (opcional, pero recomendado)

Para recibir actualizaciones de estado en tiempo real:

1. Ve a Inventario → Configuración → PedidosYa Webhooks
2. Crea una nueva configuración de webhook
3. Proporciona:
  - Nombre para la configuración
  - Transportista asociado
  - URL del webhook (accesible desde internet)
  - Clave de autorización (para mayor seguridad)
4. Haz clic en "Sync to PedidosYa" para registrar el webhook

### 4. Configurar tipos de productos

Para cada producto que será enviado:

1. Ve a la ficha del producto → pestaña Inventario
2. Establece el "Tipo de Producto PedidosYa":
  - Estándar
  - Frágil
  - Refrigerado

## Uso

### Cálculo de costos de envío en pedidos de venta

1. Crea un nuevo pedido de venta
2. Añade productos al pedido
3. Selecciona PedidosYa como método de envío
4. El costo se calculará automáticamente según la dirección de entrega

### Creación de envíos en transferencias

1. Crea o confirma un pedido de venta para generar una transferencia
2. Selecciona PedidosYa como transportista en la transferencia
3. Al validar la transferencia, se creará el envío en PedidosYa
4. El sistema guardará:
  - ID del envío (como referencia de seguimiento)
  - Código de confirmación
  - URL de seguimiento

### Seguimiento de envíos

1. Abre la transferencia relacionada con el envío
2. Visualiza el estado actual en el campo "Estado de seguimiento"
3. El estado se actualiza automáticamente mediante webhooks
4. También puedes hacer clic en el botón "Actualizar estado" para obtener actualizaciones manuales

### Generación de etiquetas

1. Selecciona una o varias transferencias con envíos de PedidosYa
2. Ve a Acciones → Obtener etiquetas de PedidosYa
3. Se generará un PDF con las etiquetas de envío

## Estados de envío

Los envíos de PedidosYa pueden tener los siguientes estados:

- **CONFIRMED:** Pedido confirmado y a la espera de ser despachado
- **IN_PROGRESS:** Se ha asignado un repartidor
- **NEAR_PICKUP:** El repartidor está cerca del punto de recogida
- **PICKED_UP:** El repartidor ha recogido el paquete
- **NEAR_DROPOFF:** El repartidor está cerca del punto de entrega
- **COMPLETED:** El repartidor ha entregado el paquete
- **CANCELLED:** El pedido ha sido cancelado

## Consideraciones técnicas

- **Coordenadas geográficas:** Para que la integración funcione correctamente, las direcciones (almacén y cliente) deben tener coordenadas geográficas (latitud y longitud).
- **Webhooks:** Para recibir actualizaciones en tiempo real, el servidor Odoo debe ser accesible desde internet. Para entornos de desarrollo, puedes usar herramientas como ngrok.
- **Campos obligatorios:** Asegúrate de que todos los contactos tengan:
 - Nombre
 - Calle
 - Ciudad
 - Teléfono
 - Coordenadas (latitud/longitud)

## Solución de problemas

Si encuentras problemas:

1. Revisa los registros de Odoo para errores relacionados con la API
2. Verifica la validez de tus credenciales de API
3. Comprueba que las direcciones tengan las coordenadas correctas
4. Asegúrate de que el webhook sea accesible desde internet

## Soporte

Para obtener ayuda con este módulo, contacta a:

- Tu representante de PedidosYa para problemas relacionados con la API
- Asteroid OMNI para problemas de implementación

## Licencia

LGPL-3

---

Desarrollado por [Asteroid OMNI](https://asteroid.cx)