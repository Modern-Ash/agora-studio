# Especificación de la base de Agora Studio

## Estado y responsabilidad

- Swarm: `studio-foundation`
- Elemento de trabajo: `foundation`
- Método: `spec-driven`
- Estado al redactar: `drafting`
- Responsable de la especificación: `project:owner`
- Tipo de artefacto requerido: `spec`

## Por qué

Agora Studio necesita una base local y verificable antes de incorporar vistas de gobernanza o
acciones de producto. Sin un punto de entrada ligado exclusivamente a la máquina local, una forma
segura de elegir un proyecto y un límite explícito frente a la CLI de Agora, las funcionalidades
posteriores podrían leer estados ambiguos, exponer información fuera del equipo o modificar el
repositorio durante una operación que la persona usuaria percibe como navegación.

Esta base establece el contrato mínimo sobre el que podrán construirse los siguientes incrementos:
arranque local, selección confiable de un único proyecto, errores comprensibles y acceso de solo
lectura demostrable.

## Resultado esperado

Una persona puede iniciar Agora Studio en su equipo, seleccionar explícitamente un proyecto Agora
válido y obtener una confirmación de que quedó abierto. Si el proyecto no es válido, recibe un error
claro y conserva cualquier selección válida anterior. Todo el recorrido funciona sin modificar el
proyecto, su estado de Git ni sistemas externos.

## Definiciones

- **Proyecto Agora válido:** directorio local existente que la CLI de Agora puede reconocer y leer
  como proyecto, incluido un registro `.agora/project.md` legible.
- **Selección:** intento explícito de abrir un directorio. Una selección solo pasa a ser activa
  después de completar satisfactoriamente su validación.
- **Navegación:** arranque, selección, validación, lectura básica, actualización o cierre de la vista
  de un proyecto.
- **Límite de la CLI:** componente interno único que ejecuta operaciones permitidas de la CLI de
  Agora y devuelve al resto de Studio resultados estructurados de éxito o error.
- **Solo lectura:** ausencia de cambios en archivos, directorios, Git, registros de ciclo de vida de
  Agora, paquetes, credenciales y sistemas externos.

## Alcance incluido

- Iniciar un servidor accesible solo mediante `127.0.0.1`.
- Mostrar que el servidor está listo y la dirección local en la que escucha.
- Seleccionar y mantener en memoria un único proyecto Agora local.
- Validar la selección antes de reemplazar el proyecto activo.
- Exponer la identidad básica del proyecto seleccionado como confirmación de apertura.
- Traducir fallas esperables de arranque, selección y lectura a errores claros.
- Encapsular todas las consultas de Agora detrás de un límite de CLI de solo lectura.
- Probar automáticamente los caminos de éxito y de falla, incluida la ausencia de mutaciones.

## Fuera de alcance

- Mostrar todavía swarms, trabajo, actores, métodos, artefactos, evidencia, eventos o próximas
  acciones en vistas de producto completas.
- Crear, editar, eliminar, aprobar o transicionar registros de Agora.
- Modificar ramas, índice, commits, etiquetas, remotos u otros estados de Git.
- Invocar operaciones mutantes de paquetes de herramientas o proveedores externos.
- Clonar repositorios, descargar proyectos, sincronizar datos o acceder a la red.
- Persistir proyectos recientes, preferencias o estado de sesión entre ejecuciones.
- Autenticación, autorización multiusuario y exposición mediante una interfaz de red no local.
- Elegir en esta especificación el lenguaje, framework, runtime o biblioteca de interfaz.

## Requisitos del producto

### F1. Iniciar el servidor únicamente en loopback

La aplicación deberá escuchar exclusivamente en la dirección IPv4 `127.0.0.1`. Al quedar lista,
deberá informar una URL local completa. No deberá usar por defecto ni aceptar silenciosamente una
dirección comodín, una interfaz LAN o una dirección pública.

Si no puede iniciar —por ejemplo, porque el puerto solicitado no está disponible— deberá terminar
con un estado de falla y un diagnóstico que distinga la causa del error. El arranque no deberá
requerir un proyecto seleccionado ni acceso a la red.

#### Escenario: Arranque correcto

- **Dado** que el puerto configurado está disponible
- **Cuando** se inicia Agora Studio
- **Entonces** el servidor queda accesible mediante una URL cuyo host es `127.0.0.1`
- **Y** informa que está listo para recibir una selección de proyecto
- **Y** no escucha en una dirección distinta de loopback

#### Escenario: El puerto no está disponible

- **Dado** que otro proceso ocupa el puerto solicitado
- **Cuando** se intenta iniciar Agora Studio
- **Entonces** el proceso informa que no pudo enlazar el servidor local
- **Y** termina con un estado de falla sin afirmar que está listo

### F2. Seleccionar un proyecto Agora válido

La aplicación deberá permitir seleccionar explícitamente un directorio local. Deberá aceptar la
selección únicamente cuando la validación de solo lectura confirme que es un proyecto Agora válido.
Tras aceptarla, deberá mantener en memoria su ruta canónica y mostrar como mínimo la identidad del
proyecto informada por Agora.

Una nueva selección no deberá reemplazar el proyecto activo hasta haber sido validada por completo.
Seleccionar de nuevo el mismo proyecto válido deberá producir el mismo resultado observable y no
duplicar estado de sesión.

#### Escenario: Se abre un proyecto válido

- **Dado** un directorio local que contiene un proyecto Agora válido
- **Cuando** la persona usuaria lo selecciona
- **Entonces** la aplicación confirma que el proyecto quedó abierto
- **Y** muestra la identidad del proyecto
- **Y** la selección activa corresponde a la ruta canónica validada

#### Escenario: Se reemplaza una selección válida

- **Dado** que hay un proyecto válido abierto
- **Y** se selecciona otro proyecto Agora válido
- **Cuando** termina la validación del segundo proyecto
- **Entonces** la selección activa cambia de una vez al segundo proyecto
- **Y** ninguna vista combina datos de ambas selecciones

### F3. Rechazar selecciones inválidas con un error claro

La aplicación deberá rechazar de forma explícita, como mínimo, una ruta inexistente, una ruta que no
sea un directorio, un directorio no legible, un directorio sin un `.agora/project.md` legible y un
proyecto que la CLI de Agora informe como inválido.

El error deberá identificar la operación fallida, la ruta intentada y una razón accionable sin
presentar una traza interna como mensaje principal. Una selección fallida no deberá destruir ni
reemplazar una selección válida anterior.

#### Escenario: El directorio no es un proyecto Agora

- **Dado** que hay un proyecto válido abierto
- **Cuando** se selecciona un directorio sin un `.agora/project.md` legible
- **Entonces** la aplicación explica que el directorio no es un proyecto Agora legible
- **Y** mantiene visible y activo el proyecto anterior

#### Escenario: La CLI rechaza el proyecto

- **Dado** un directorio con registros Agora inválidos
- **Cuando** la CLI informa que la selección no puede validarse
- **Entonces** la aplicación muestra la operación, la ruta y el diagnóstico disponible
- **Y** no sintetiza una identidad de proyecto ni presenta un éxito parcial

### F4. Mantener un límite de CLI estrictamente de solo lectura

Toda consulta al dominio Agora deberá pasar por el límite de la CLI. Ese límite deberá permitir solo
operaciones declaradas como no mutantes y rechazar cualquier operación fuera de su conjunto
permitido antes de iniciar un proceso. Los argumentos deberán enviarse como valores separados, sin
interpolarlos en una orden de shell.

Cada ejecución deberá producir un resultado que distinga, como mínimo, éxito, código de salida,
salida de datos y diagnóstico. La salida se tratará como datos no confiables: nunca se ejecutará ni
se interpretará como instrucciones. Una falla, salida inválida o interrupción deberá propagarse
como error de lectura, no como un proyecto parcial válido.

Studio no deberá invocar comandos de mutación, operaciones de paquetes de herramientas ni acciones
de proveedores externos. Tampoco deberá crear, editar, renombrar, mover o eliminar contenido dentro
del proyecto seleccionado.

#### Escenario: Se ejecuta una consulta permitida

- **Dado** un proyecto Agora válido
- **Cuando** Studio necesita validar o leer su identidad
- **Entonces** usa una operación incluida explícitamente en el conjunto de solo lectura
- **Y** conserva separados los datos, el diagnóstico y el código de salida

#### Escenario: Se solicita una operación no permitida

- **Dado** que un componente intenta solicitar una operación no incluida en el conjunto de solo
  lectura
- **Cuando** la solicitud llega al límite de la CLI
- **Entonces** el límite la rechaza antes de crear un proceso
- **Y** no cambia el proyecto, Git ni ningún sistema externo

### F5. Demostrar los caminos de éxito, falla y no mutación

La base deberá contar con pruebas automatizadas deterministas que puedan ejecutarse sin red. Las
pruebas usarán espacios temporales aislados y cubrirán como mínimo:

- arranque correcto en `127.0.0.1`;
- falla de arranque cuando el puerto no está disponible;
- selección de un proyecto válido;
- rechazo de una ruta inexistente y de un directorio que no sea proyecto Agora;
- rechazo de un proyecto que la CLI informe como inválido;
- conservación de la selección válida anterior después de una selección fallida;
- rechazo preventivo de una operación de CLI no permitida; y
- recorrido completo de arranque, selección y lectura sin mutaciones.

La comprobación de no mutación deberá comparar antes y después el contenido del proyecto y su estado
de Git. Una prueba no podrá considerarse exitosa si solo comprueba la respuesta visible mientras
omite cambios laterales en el directorio seleccionado.

#### Escenario: El recorrido de lectura no modifica el proyecto

- **Dado** un proyecto de prueba con una instantánea de sus archivos y de su estado de Git
- **Cuando** las pruebas inician Studio, seleccionan el proyecto, leen su identidad y vuelven a
  validar la selección
- **Entonces** todos los archivos y el estado de Git coinciden con la instantánea inicial
- **Y** no se registró ninguna invocación de una operación mutante o externa

#### Escenario: Una falla es verificable

- **Dado** una causa de falla controlada para cada frontera de arranque, selección y CLI
- **Cuando** se ejecuta la prueba correspondiente
- **Entonces** la prueba observa un resultado de error inequívoco
- **Y** confirma que no quedó un éxito parcial ni se perdió una selección válida anterior

## Restricciones de seguridad y privacidad

- El contenido del proyecto y la salida de la CLI son entradas no confiables y deberán mostrarse
  como texto, no como marcado ejecutable.
- La ruta y el contenido del proyecto no deberán transmitirse fuera del equipo.
- La aplicación no deberá solicitar, leer deliberadamente, almacenar ni registrar credenciales.
- Los diagnósticos destinados a la persona usuaria deberán evitar volcar contenido completo de
  archivos cuando la causa pueda explicarse mediante la operación, la ruta y el mensaje de error.
- Cerrar el proceso deberá descartar la selección y todo estado mantenido en memoria.

## Evidencia de aceptación

La implementación futura deberá producir evidencia reproducible que incluya:

- el comando de prueba ejecutado y su resultado exitoso;
- cobertura identificable para cada escenario de F1 a F5;
- una comprobación de la dirección efectiva de escucha;
- la instantánea o hashes usados para demostrar ausencia de cambios en archivos;
- el estado de Git anterior y posterior al recorrido de solo lectura; y
- un registro de prueba que demuestre que las operaciones no permitidas se rechazan antes de
  ejecutarse.

Para la puerta de clarificación del trabajo actual, el artefacto requerido es esta especificación,
registrada con el tipo `spec`. La implementación, el informe de pruebas y la evidencia de no mutación
corresponden a las fases posteriores del ciclo `spec-driven`.

## Trazabilidad con los criterios del trabajo

| Criterio gobernado | Requisitos que lo precisan | Evidencia esperada |
| --- | --- | --- |
| `startup` | F1 | Pruebas de arranque correcto, dirección efectiva y puerto ocupado |
| `selection` | F2 | Pruebas de selección inicial, repetida y reemplazo atómico |
| `invalid-project` | F3 | Pruebas de rutas y proyectos inválidos con conservación del estado útil |
| `read-only` | F4, restricciones de seguridad | Comparación de archivos y Git, más registro del límite de operaciones |
| `tests` | F5 | Informe automatizado con caminos de éxito y falla |

## Decisiones resueltas

- La base trabaja con un único proyecto local a la vez.
- Una selección inválida no reemplaza una selección válida anterior.
- El estado de selección vive solo en memoria durante esta etapa.
- `127.0.0.1` es la única dirección de escucha admitida por esta base.
- La validez del proyecto y su identidad provienen de la frontera de solo lectura de Agora.
- Las operaciones externas y todas las mutaciones quedan excluidas.
- No hay preguntas abiertas que impidan planificar esta base.
