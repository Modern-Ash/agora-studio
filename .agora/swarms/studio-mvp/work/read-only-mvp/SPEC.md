# Especificación del MVP de solo lectura de Agora Studio

## Estado y responsabilidad

- Swarm: `studio-mvp`
- Elemento de trabajo: `read-only-mvp`
- Método: `spec-driven`
- Estado al redactar: `drafting`
- Responsable de la especificación: `project:owner`

## Por qué

Los proyectos Agora almacenan su estado de gobernanza autoritativo como registros Markdown
interrelacionados e historial de Git. Esos registros son revisables, pero comprender la situación
actual de un proyecto exige conocer la estructura de directorios, seguir referencias entre archivos
e interpretar las reglas del paquete de método o los resultados de varios comandos de la CLI.

El MVP de solo lectura brinda a responsables de proyecto, desarrolladores y revisores una vista
local coherente de ese estado. Reduce el esfuerzo necesario para saber qué es el proyecto, quién es
responsable, qué trabajo está activo, por qué está bloqueado, qué evidencia existe, si el espacio de
trabajo es válido y qué acción gobernada está disponible a continuación.

## Resultado esperado

Una persona puede abrir un proyecto Agora local, inspeccionar su estado de gobernanza y entrega,
diagnosticar registros inválidos o incompletos y ver las próximas acciones atribuidas por rol, sin
que Agora Studio modifique el proyecto ni contacte sistemas externos.

## Límite de solo lectura

Para este MVP, solo lectura significa que Agora Studio:

- no crea, edita, renombra, mueve ni elimina archivos del proyecto;
- no cambia ramas, índice, commits, etiquetas, remotos ni contenido del árbol de trabajo de Git;
- no invoca mutaciones del ciclo de vida de Agora, operaciones de paquetes de herramientas ni
  acciones de proveedores externos;
- no solicita, almacena ni transmite credenciales del proyecto;
- mantiene selecciones, filtros, filas expandidas y estados de vista similares únicamente en
  memoria; y
- trata el contenido del proyecto como datos no confiables para mostrar, nunca como instrucciones
  ejecutables.

La inspección de solo lectura puede invocar comandos cuyo comportamiento declarado sea no mutante,
incluidos estado, validación, listados, visualización de registros, historial de eventos, bandeja de
entrada y consultas de próximas acciones. El producto no debe asumir que un comando es seguro solo
porque su nombre parezca descriptivo.

## Personas usuarias

- La persona responsable del proyecto necesita una visión general de su salud, estado del trabajo,
  responsabilidades y decisiones.
- Una persona desarrolladora necesita comprender el trabajo asignado, su estado actual en el
  paquete de método, sus bloqueos y la próxima acción disponible para el rol de desarrollo.
- Una persona revisora necesita acceso trazable a criterios, artefactos, evidencia, aprobaciones e
  historial de eventos.

## Alcance incluido

- Abrir un directorio local seleccionado explícitamente como proyecto Agora.
- Inspeccionar proyectos, paquetes de método, actores, swarms, trabajo, artefactos, evidencia,
  aprobaciones y eventos.
- Mostrar resultados de validación y orientar sobre próximas acciones atribuidas por rol.
- Actualizar manualmente y presentar con claridad estados vacíos, desactualizados, no disponibles e
  inválidos.
- Ofrecer una interfaz orientada a escritorio que siga siendo utilizable en los tamaños de ventana
  compatibles y mediante teclado.

## Fuera de alcance

- Cualquier mutación del proyecto, Git, el ciclo de vida de Agora, los paquetes de herramientas o
  sistemas externos.
- Editar especificaciones u otros archivos Markdown desde la aplicación.
- Ejecutar acciones de planificación, implementación, verificación, aprobación, traspaso,
  delegación o finalización.
- Clonar repositorios, navegar contenido remoto, colaborar, sincronizar o almacenar en la nube.
- Autenticar, gestionar credenciales, instalar registros o paquetes y configurar entornos.
- Combinar o comparar varios proyectos en una misma vista.
- Diseños específicos para dispositivos móviles y aplicaciones móviles nativas.

## Requisitos del producto

### R1. Abrir un proyecto Agora

El producto deberá permitir que la persona usuaria seleccione un directorio local y deberá
aceptarlo únicamente cuando contenga un registro `.agora/project.md` legible. Abrir otro directorio
deberá reemplazar la vista actual en memoria solo después de que el nuevo directorio haya sido
aceptado.

#### Escenario: Se abre un proyecto válido

- **Dado** que se selecciona un directorio con un `.agora/project.md` legible
- **Cuando** finaliza la operación de apertura
- **Entonces** el producto muestra la identidad y la visión general de gobernanza del proyecto
- **Y** el directorio seleccionado permanece sin cambios

#### Escenario: Se rechaza un directorio inválido

- **Dado** que hay un proyecto válido abierto
- **Cuando** se selecciona un directorio sin un `.agora/project.md` legible
- **Entonces** el producto explica que el directorio no es un proyecto Agora legible
- **Y** el proyecto abierto continúa visible y sin cambios

### R2. Mostrar la identidad y la salud del proyecto

La visión general deberá mostrar el identificador del proyecto, la integración, el paquete de método
predeterminado, la rama actual de Git cuando esté disponible, los conteos agregados de registros, los
totales por estado de swarm, los totales por estado del paquete de método para el trabajo, los totales
por estado operativo y los elementos que requieren atención. El estado del paquete de método y el
estado operativo deberán presentarse como conceptos diferentes.

#### Escenario: Visión general de un proyecto saludable

- **Dado** un proyecto abierto cuyo resultado de validación no contiene problemas
- **Cuando** se muestra la visión general
- **Entonces** son visibles la identidad, la rama, los conteos, los totales por estado y un resultado
  de salud válido
- **Y** los estados del paquete de método no se combinan con estados operativos bloqueados o
  cancelados

### R3. Explicar el método gobernante

El producto deberá mostrar el paquete de método activo del swarm seleccionado, sus estados de trabajo
ordenados, el estado terminal, los roles requeridos, las transiciones y las puertas asociadas con
esas transiciones.

#### Escenario: Se inspecciona un swarm gobernado por especificaciones

- **Dado** un swarm seleccionado gobernado por `spec-driven`
- **Cuando** se abre su vista de método
- **Entonces** se muestran en orden los estados desde `drafting` hasta `completed`
- **Y** las transiciones gobernadas identifican su puerta y el rol responsable

### R4. Listar e inspeccionar actores y asignaciones de roles

El producto deberá mostrar los actores visibles para el proyecto, su alcance, tipo, capacidades
declaradas y requisito de autenticación. Para cada swarm, deberá mostrar todos los roles requeridos y
el actor asignado, incluidos los roles sin asignación.

#### Escenario: Las asignaciones del swarm son visibles

- **Dado** un swarm con roles requeridos asignados y sin asignar
- **Cuando** se inspeccionan las asignaciones
- **Entonces** cada rol requerido se muestra una sola vez
- **Y** cada rol indica el actor asignado o que permanece sin asignar

### R5. Listar swarms sin ocultar su estado de ciclo de vida

El producto deberá listar todos los swarms del proyecto con su objetivo, método, rama, estado de
ciclo de vida y grado de completitud de las asignaciones. Los swarms en formación, preparados,
activos, completados y cancelados deberán seguir siendo localizables y distinguirse visualmente.

#### Escenario: Un swarm terminal sigue siendo inspeccionable

- **Dado** que el proyecto contiene un swarm cancelado o completado
- **Cuando** se consulta la lista de swarms
- **Entonces** el swarm continúa disponible para inspección
- **Y** su estado terminal es explícito

### R6. Listar y filtrar trabajo

El producto deberá listar el trabajo del proyecto abierto y permitir filtros en memoria por swarm,
estado del paquete de método, estado operativo y rol o actor asignado cuando sea posible derivar la
asignación. Cada fila deberá mostrar como mínimo el identificador, título, swarm, estado, estado
operativo y resumen de puertas incumplidas.

#### Escenario: Se aísla el trabajo bloqueado

- **Dado** que el proyecto contiene trabajo activo y bloqueado
- **Cuando** se filtra por estado operativo bloqueado
- **Entonces** solo se muestra el trabajo bloqueado
- **Y** permanece visible el estado del paquete de método de cada resultado

### R7. Mostrar un detalle de trabajo trazable

El detalle deberá mostrar la descripción, el estado actual del paquete de método, el estado operativo
y su motivo, los criterios de aceptación con su estado de satisfacción, los tipos de artefactos
requeridos y registrados, los resultados de evidencia, las aprobaciones, las referencias a trabajo
padre e hijo, la referencia de delegación y el historial durable de estados cuando exista. Cada
registro local referenciado deberá exponer su ruta relativa al proyecto.

#### Escenario: Se explica un trabajo incompleto

- **Dado** un elemento de trabajo con criterios sin satisfacer y un artefacto requerido faltante
- **Cuando** se abre su detalle
- **Entonces** los criterios sin satisfacer y el tipo de artefacto faltante pueden identificarse por
  separado
- **Y** son visibles las rutas de origen de los registros subyacentes

### R8. Inspeccionar artefactos, evidencia y aprobaciones

El producto deberá presentar los URI de artefactos, los resultados de evidencia y sus referencias a
artefactos, y los registros de aprobación sin insinuar que la mera existencia equivale a éxito o
aceptación. Los registros faltantes deberán mostrarse como tales, sin sintetizarlos a partir de la
conversación o del estado de proyectos vecinos.

#### Escenario: La evidencia fallida no se presenta como finalización

- **Dado** un elemento de trabajo con un artefacto registrado y evidencia fallida
- **Cuando** se inspeccionan los registros de entrega
- **Entonces** el artefacto se muestra como registrado
- **Y** la evidencia fallida se distingue visualmente de la evidencia exitosa y de la aprobación

### R9. Mostrar el historial de eventos atribuidos

El producto deberá mostrar los eventos del proyecto, del swarm y del trabajo seleccionado en orden
cronológico, con fecha y hora, tipo de evento, detalle, alcance y ruta de origen. No deberá inferir
eventos ausentes de los registros durables.

#### Escenario: Se rastrea un cambio de estado

- **Dado** que existen eventos durables para un cambio de estado de trabajo
- **Cuando** se consulta la cronología correspondiente
- **Entonces** la transición se muestra con la fecha y hora, tipo, detalle, alcance y origen
  registrados

### R10. Informar fielmente la validación

El producto deberá permitir ejecutar la validación del proyecto y mostrar el resultado general junto
con la gravedad, el código exacto, la ruta relativa al proyecto y el mensaje de cada problema
informado. Los errores de validación no deberán repararse en silencio, descartarse ni reemplazarse
con datos inferidos.

#### Escenario: Se informa una referencia inválida entre registros

- **Dado** que la validación informa un error de referencia entre registros
- **Cuando** se muestra la vista de validación
- **Entonces** son visibles la gravedad, el código, la ruta y el mensaje del error
- **Y** el producto no ofrece una acción de reparación automática

### R11. Mostrar próximas acciones atribuidas por rol

El producto deberá mostrar las próximas acciones gobernadas informadas para un actor visible
seleccionado, incluidos el swarm, el trabajo, el rol, el estado actual, los estados de destino, los
bloqueos y el motivo. Un resultado vacío deberá presentarse como ausencia de acciones gobernadas
disponibles, no como finalización exitosa.

#### Escenario: Un trabajo en redacción está bloqueado por su puerta

- **Dado** que una persona responsable de especificación tiene trabajo en `drafting` con condiciones
  incumplidas de la puerta de clarificación
- **Cuando** se consultan las próximas acciones para ese actor
- **Entonces** se muestra la continuación del trabajo de especificación
- **Y** cada bloqueo informado por la puerta es visible sin reinterpretación

#### Escenario: El actor no tiene una próxima acción

- **Dado** que la consulta de próximas acciones no devuelve entradas para un actor
- **Cuando** se muestra la vista correspondiente
- **Entonces** el producto indica que actualmente no hay una acción gobernada disponible para ese
  actor

### R12. Actualizar sin producir un estado mezclado

El producto deberá ofrecer actualización manual. Cada actualización completada deberá reemplazar de
forma atómica la instantánea visible del proyecto, de modo que los registros de dos actualizaciones
no se presenten como un único estado coherente. Mientras haya una actualización en curso, el
producto deberá identificar los datos visibles como pertenecientes a la instantánea anterior.

#### Escenario: Los archivos cambian entre actualizaciones

- **Dado** que el proyecto cambia fuera de Agora Studio después de cargar una instantánea
- **Cuando** la actualización manual finaliza correctamente
- **Entonces** todas las vistas utilizan la nueva instantánea completa
- **Y** ninguna vista combina detalles antiguos del trabajo con el nuevo estado agregado

### R13. Conservar el estado útil cuando falla una lectura

Si falla una actualización, validación o consulta acotada de solo lectura, el producto deberá
conservar la última instantánea completa, marcarla como posiblemente desactualizada y mostrar la
operación fallida y el mensaje de diagnóstico disponible. No deberá inventar registros faltantes ni
reemplazar la vista con un éxito parcial.

#### Escenario: Falla la actualización

- **Dado** que hay una instantánea completa del proyecto visible
- **Cuando** falla una actualización posterior
- **Entonces** la instantánea anterior continúa siendo inspeccionable y se marca como posiblemente
  desactualizada
- **Y** la falla es visible sin afirmar que se modificó el proyecto

### R14. Gestionar estados vacíos legítimos

El producto deberá distinguir una colección vacía de una falla de lectura. Como mínimo, deberá
proporcionar estados vacíos explícitos para ausencia de trabajo, evidencia, aprobaciones, eventos en
el alcance seleccionado, problemas de validación, elementos que requieren atención y próximas
acciones.

#### Escenario: Un proyecto nuevo no tiene trabajo

- **Dado** un proyecto válido sin elementos de trabajo
- **Cuando** se muestra la vista de trabajo
- **Entonces** el producto indica que no existe trabajo
- **Y** no presenta esa condición como un error

### R15. Garantizar la ausencia de mutaciones

El producto no deberá exponer controles de interfaz, comandos de teclado, enlaces profundos,
comportamientos de inicio ni operaciones en segundo plano que puedan modificar archivos del
proyecto, el estado de Git, el ciclo de vida de Agora, los paquetes instalados, sistemas externos o
credenciales.

#### Escenario: El recorrido completo de solo lectura no cambia las fuentes

- **Dado** que se registraron los hashes y el estado de Git de un proyecto de prueba representativo
- **Cuando** una persona abre el proyecto, navega todas las vistas del MVP, filtra trabajo, valida,
  consulta próximas acciones y actualiza
- **Entonces** todos los hashes de los archivos del proyecto y el estado de Git son idénticos a la
  línea de base
- **Y** no se invocó ninguna operación mutante de Agora ni de paquetes de herramientas

### R16. Mantener locales los datos del proyecto

El producto deberá permitir completar todo el recorrido del MVP sin acceso a la red y no deberá
transmitir rutas, contenido, metadatos, diagnósticos ni telemetría de uso del proyecto.

#### Escenario: La aplicación funciona sin red disponible

- **Dado** que no hay acceso a la red
- **Cuando** se completa el recorrido representativo de solo lectura
- **Entonces** todas las vistas y consultas incluidas en el alcance continúan utilizables
- **Y** ninguna funcionalidad solicita credenciales ni conexión en línea

### R17. Tratar el contenido mostrado como no confiable

El Markdown, las etiquetas, las rutas, los URI, los detalles de eventos y los mensajes de diagnóstico
provistos por el proyecto deberán representarse como contenido inerte. No deberán ejecutar scripts,
fragmentos de shell, HTML embebido, comandos ni enlaces abiertos automáticamente.

#### Escenario: El proyecto contiene texto con apariencia ejecutable

- **Dado** que un campo del proyecto contiene marcado, un fragmento de shell o un URI externo
- **Cuando** se muestra el campo
- **Entonces** su contenido no puede ejecutarse ni abrirse automáticamente
- **Y** inspeccionarlo no modifica el proyecto

### R18. Cumplir una base de accesibilidad

Toda la navegación, selección de proyectos, actualización, filtrado e inspección de detalles dentro
del alcance deberá ser utilizable únicamente con teclado. Los elementos interactivos deberán tener
nombres determinables programáticamente, el foco deberá ser visible, el estado no deberá depender
solo del color y el texto y los indicadores visuales esenciales deberán cumplir los umbrales de
contraste WCAG 2.2 AA.

#### Escenario: Inspección únicamente con teclado

- **Dado** que hay un proyecto válido abierto
- **Cuando** una persona utiliza el producto sin dispositivo apuntador
- **Entonces** puede alcanzar y operar todos los controles incluidos e inspeccionar todas las vistas
  incluidas
- **Y** la posición del foco y el significado de los estados siguen siendo perceptibles

### R19. Seguir siendo utilizable en tamaños de escritorio compatibles

La interfaz deberá seguir siendo completamente operable sin desplazamiento horizontal de página en
anchos de viewport de 1024 a 1920 píxeles CSS y alturas de al menos 720 píxeles CSS. Los registros
densos podrán desplazarse dentro de su región de contenido designada.

#### Escenario: Viewport mínimo compatible

- **Dado** un viewport de 1024 por 720 píxeles CSS
- **Cuando** se abre cada vista incluida en el alcance
- **Entonces** todos los controles principales y campos de registros permanecen accesibles
- **Y** la página no requiere desplazamiento horizontal

### R20. Ofrecer un rendimiento interactivo acotado

Con el proyecto de prueba de aceptación definido a continuación, el 95 % de las operaciones de
apertura y actualización manual deberá presentar una instantánea completa dentro de 2 segundos, y
el 95 % de las actualizaciones de navegación y filtros en memoria deberá presentar su resultado
dentro de 100 milisegundos. Las mediciones excluyen el tiempo empleado en el selector de directorios
del sistema operativo.

#### Escenario: El proyecto de prueba cumple los umbrales de latencia

- **Dado** el proyecto de prueba de aceptación y un entorno de referencia sin otra carga
- **Cuando** se miden 20 aperturas, 20 actualizaciones y 100 cambios de navegación o filtros
- **Entonces** al menos el 95 % de las aperturas y actualizaciones finaliza dentro de 2 segundos
- **Y** al menos el 95 % de los cambios de navegación y filtros finaliza dentro de 100 milisegundos

## Proyecto de prueba de aceptación

La verificación deberá incluir un proyecto local, versionado y sin credenciales que contenga:

- 1 proyecto con constitución y el paquete de método `spec-driven` instalado;
- al menos 4 actores con alcance de proyecto y de usuario;
- al menos 3 swarms que cubran estados en formación o preparados, activos y terminales;
- al menos 100 elementos de trabajo que cubran todos los estados del paquete de método y estados
  operativos activos, bloqueados y cancelados;
- al menos una relación de trabajo padre-hijo y una referencia de delegación;
- criterios satisfechos y sin satisfacer, artefactos requeridos presentes y faltantes, evidencia
  exitosa y fallida, y aprobaciones presentes y ausentes;
- al menos 1.000 eventos atribuidos entre los alcances de proyecto, swarm y trabajo; y
- un proyecto inválido separado con al menos un problema de validación que contenga un código y una
  ruta estables.

El hardware, el sistema operativo, la versión de la CLI de Agora y el método de medición del entorno
de referencia deberán registrarse junto con la evidencia de rendimiento para que los resultados
sean reproducibles.

## Medidas de finalización para el futuro incremento del MVP

- Todos los escenarios de requisitos pasan con los proyectos de prueba de aceptación.
- El recorrido sin mutaciones demuestra que los hashes de los archivos y el estado de Git no
  cambiaron.
- El producto funciona con la red deshabilitada y no produce solicitudes salientes.
- Las comprobaciones de accesibilidad cubren reglas WCAG automatizadas y el recorrido solo con
  teclado.
- La evidencia de rendimiento registra el proyecto de prueba, el entorno, las cantidades de muestras
  y los percentiles observados.
- Toda limitación descubierta durante la verificación se resuelve o se devuelve a implementación; no
  se convierte silenciosamente en una excepción de la especificación.

## Decisiones de producto resueltas

- El MVP abre un proyecto por vez.
- La selección del proyecto es explícita; no se realiza un escaneo automático del sistema de
  archivos.
- La actualización es manual; no se requiere observación de archivos en tiempo real.
- Se permite estado de interfaz en memoria, pero no preferencias persistentes ni historial de
  proyectos recientes.
- Los problemas de validación y las próximas acciones se presentan tal como fueron informados, sin
  reparación automática ni recomendaciones sintéticas.
- El MVP solo admite tamaños de viewport de escritorio.
- Los flujos de trabajo mutantes se postergan para un incremento especificado por separado.

## Preguntas abiertas

Ninguna.
