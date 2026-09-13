# Despliegue de Mi Amigo Max en AWS AgentCore

> **Nota importante:** El despliegue en AgentCore es completamente **opcional**.
> Mi Amigo Max funciona en su totalidad de forma local ejecutando `python app.py`
> o `streamlit run streamlit_app.py`, sin necesidad de ningún servicio en la nube
> más allá de las llamadas al modelo en Amazon Bedrock.
> Sigue estas instrucciones solo si quieres un despliegue gestionado en AWS.

---

## Prerrequisitos

- AWS CLI instalado y configurado (`aws configure`)
- Permisos IAM para: `bedrock:InvokeModel`, `agentcore:CreateAgent`, `agentcore:InvokeAgent`, `s3:PutObject`, `ecr:*`
- Docker instalado y en ejecución
- Python 3.11+ y el paquete `strands-agents` instalado

---

## Pasos para el despliegue

1. **Verifica los prerrequisitos de AWS AgentCore**

   Consulta la documentación oficial y asegúrate de que AgentCore esté disponible en tu región:
   ```bash
   aws agentcore list-agents --region us-east-1
   ```

2. **Empaqueta la aplicación en una imagen Docker**

   Crea el archivo `Dockerfile` en la raíz del proyecto:
   ```dockerfile
   FROM python:3.11-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   COPY . .
   ENV DB_PATH=/tmp/max_data.db
   CMD ["python", "app.py"]
   ```

   Construye la imagen:
   ```bash
   docker build -t mi-amigo-max:latest .
   ```

3. **Publica la imagen en Amazon ECR**

   Crea el repositorio ECR si no existe:
   ```bash
   aws ecr create-repository --repository-name mi-amigo-max --region us-east-1
   ```

   Autentica Docker con ECR y sube la imagen:
   ```bash
   aws ecr get-login-password --region us-east-1 \
     | docker login --username AWS \
       --password-stdin <CUENTA_AWS>.dkr.ecr.us-east-1.amazonaws.com

   docker tag mi-amigo-max:latest \
     <CUENTA_AWS>.dkr.ecr.us-east-1.amazonaws.com/mi-amigo-max:latest

   docker push \
     <CUENTA_AWS>.dkr.ecr.us-east-1.amazonaws.com/mi-amigo-max:latest
   ```

4. **Configura las variables de entorno en AWS Secrets Manager**

   Almacena las variables sensibles como secreto:
   ```bash
   aws secretsmanager create-secret \
     --name mi-amigo-max/config \
     --secret-string '{
       "AWS_REGION": "us-east-1",
       "BEDROCK_MODEL_ID": "anthropic.claude-3-5-sonnet-20241022-v2:0",
       "DB_PATH": "/tmp/max_data.db"
     }'
   ```

5. **Crea el agente en AgentCore**

   Usando el SDK de Strands con soporte AgentCore:
   ```python
   from strands.agent.agentcore import AgentCoreConfig  # type: ignore

   config = AgentCoreConfig(
       agent_name="mi-amigo-max",
       description="Agente conversacional de acompañamiento para adultos mayores",
       image_uri="<CUENTA_AWS>.dkr.ecr.us-east-1.amazonaws.com/mi-amigo-max:latest",
       region="us-east-1",
   )
   config.deploy()
   ```

   O mediante la CLI de AWS (cuando AgentCore CLI esté disponible):
   ```bash
   aws agentcore create-agent \
     --agent-name mi-amigo-max \
     --description "Agente de acompañamiento" \
     --container-image <URI_ECR>
   ```

6. **Verifica el despliegue**

   ```bash
   aws agentcore list-agents --region us-east-1
   aws agentcore get-agent --agent-name mi-amigo-max
   ```

7. **Prueba el agente desplegado**

   Invoca el agente con un mensaje de prueba:
   ```bash
   aws agentcore invoke-agent \
     --agent-name mi-amigo-max \
     --input-text "Hola Max, ¿cómo estás?"
   ```

8. **Configura monitoreo y logs (recomendado)**

   Habilita CloudWatch Logs para el agente:
   ```bash
   aws agentcore update-agent \
     --agent-name mi-amigo-max \
     --logging-config '{"cloudwatchLogGroup": "/agentcore/mi-amigo-max", "level": "INFO"}'
   ```

---

## Consideraciones de almacenamiento en la nube

Al desplegar en AgentCore, la base de datos SQLite local (`DB_PATH=/tmp/max_data.db`) se perderá entre reinicios del contenedor. Para persistencia duradera en la nube, considera:

- **Amazon EFS**: monta un sistema de archivos persistente en el contenedor.
- **Amazon RDS (PostgreSQL)**: migra la capa de datos reemplazando `db/models.py` con un adaptador PostgreSQL.
- **Amazon DynamoDB**: reemplaza SQLite con DynamoDB para escala horizontal.

La migración de la capa de datos es el único cambio de código necesario; toda la lógica del agente permanece igual.

---

## Recursos adicionales

- [Documentación oficial de Strands Agents SDK](https://strandsagents.dev)
- [Amazon Bedrock — Modelos disponibles](https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html)
- [AWS AgentCore (preview)](https://aws.amazon.com/agentcore/)
