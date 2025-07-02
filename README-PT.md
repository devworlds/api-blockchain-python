# API Blockchain Python

![Generic badge](https://img.shields.io/badge/maintainer-devworlds-blue.svg)
[![codecov](https://codecov.io/gh/devworlds/api-blockchain-python/branch/main/graph/badge.svg)](https://codecov.io/gh/devworlds/api-blockchain-python)
[![CI](https://github.com/devworlds/api-blockchain-python/actions/workflows/ci.yml/badge.svg)](https://github.com/devworlds/api-blockchain-python/actions/workflows/ci.yml)
![Generic badge](https://img.shields.io/badge/version-v0.1.0-green.svg)

Uma API REST segura e escalável para gerenciamento de transações blockchain construída com FastAPI, apresentando criação de carteiras, processamento de transações e validação on-chain com padrões de segurança de nível empresarial.

## Visão Geral da Arquitetura

Este projeto implementa uma **Arquitetura Limpa** com princípios de **Design Orientado a Domínio (DDD)**, garantindo separação de responsabilidades, testabilidade e manutenibilidade.

### Camadas da Arquitetura

```
├── app/
│   ├── application/          # Camada de Aplicação (Casos de Uso, Handlers, Schemas)
│   │   └── v1/
│   │       ├── transaction/  # Módulo de funcionalidade de transação
│   │       └── wallet/       # Módulo de funcionalidade de carteira
│   ├── domain/              # Camada de Domínio (Entidades, Interfaces de Repository)
│   │   ├── transaction/
│   │   └── wallet/
│   ├── infrastructure/      # Camada de Infraestrutura (Integrações externas)
│   │   ├── blockchain/      # Integrações Web3
│   │   ├── db/             # Implementações de banco de dados
│   │   └── config.py       # Gerenciamento de configuração
│   └── shared/             # Utilitários compartilhados
└── tests/                  # Testes unitários (98% cobertura)
```

## Principais Funcionalidades

### Segurança em Primeiro Lugar
- **Integração com HashiCorp Vault** para gerenciamento de chaves privadas
- **Nenhuma chave privada armazenada no banco de dados** - chaves protegidas no Vault
- **Assinatura de transações** acontece de forma segura via Vault
- **Operações assíncronas** para alta concorrência

### Integração Blockchain
- **Conectividade Web3 real** (suporte Mainnet/Testnet)
- **Suporte a transações ETH e tokens ERC20**
- **Validação de confirmação de transação** com limites configuráveis
- **Verificação de transação on-chain**

### Banco de Dados e Persistência
- **PostgreSQL** com pool de conexão assíncrona
- **SQLAlchemy ORM** com migrações adequadas
- **Histórico de transações** com rastreamento de status
- **Soft deletes** para trilhas de auditoria

### Monitoramento e Observabilidade
- **Métricas Prometheus** para monitoramento abrangente
- **Dashboards Grafana** para visualização
- **Logging JSON estruturado** com Structlog + Loguru
- **Rastreamento de performance em tempo real** para todas as operações
- **Métricas de negócio** para analytics de transações

## Stack Tecnológico

- **FastAPI** - Framework web assíncrono moderno
- **Web3.py** - Interação com blockchain Ethereum
- **HashiCorp Vault** - Gerenciamento de segredos
- **PostgreSQL** - Banco de dados principal
- **SQLAlchemy** - ORM com suporte assíncrono
- **Alembic** - Migrações de banco de dados
- **Pytest** - Framework de testes (98% cobertura)
- **Docker** - Containerização

**Stack de Monitoramento:**
- **Prometheus** - Coleta e armazenamento de métricas
- **Grafana** - Visualização e dashboards
- **Structlog + Loguru** - Logging estruturado
- **FastAPI Instrumentator** - Métricas automáticas da API

## Padrões de Design e Princípios

### Por Que Esses Padrões?

1. **Arquitetura Limpa**: Garante independência da lógica de negócios de frameworks externos
2. **Padrão Repository**: Abstrai acesso a dados, permitindo fácil teste e troca de implementações
3. **Injeção de Dependência**: Promove baixo acoplamento e testabilidade
4. **Padrão Use Case**: Encapsula lógica de negócios em componentes reutilizáveis
5. **Módulos baseados em Features**: Organiza código por funcionalidades de negócio em vez de camadas técnicas

### Benefícios
- **Alta Testabilidade** (98% cobertura de teste alcançada)
- **Fácil Manutenção** - Clara separação de responsabilidades
- **Escalabilidade** - Design async-first
- **Segurança** - Integração Vault para dados sensíveis
- **Flexibilidade** - Fácil troca de implementações

## Endpoints da API

### Gerenciamento de Carteiras

#### Criar Carteiras
```http
POST /v1/wallets
Content-Type: application/json

{
  "n": 5
}
```
**Resposta:**
```json
{
  "addresses": ["0xabc...", "0xdef..."],
  "status": "success"
}
```

#### Listar Todas as Carteiras
```http
GET /v1/wallets
```

### Gerenciamento de Transações

#### Criar Transação On-Chain

```http
POST /v1/transaction
Content-Type: application/json

{
  "address_from": "0x742d35Cc6554C65532e42C8b24fd213ee707b96",
  "address_to": "0x8ba1f109551bD432803012645Hac136c",
  "asset": "ETH",
  "value": "0.001",
  "contract_address": null
}
```

**Para Tokens ERC20:**
```json
{
  "address_from": "0x742d35Cc6554C65532e42C8b24fd213ee707b96",
  "address_to": "0x8ba1f109551bD432803012645Hac136c",
  "asset": "USDT",
  "value": "10.5",
  "contract_address": "0xdAC17F958D2ee523a2206206994597C13D831ec7"
}
```

**Opções de Formato de Valor:**
- **String decimal** (recomendado): `"0.0001"`
- **Float**: `0.0001`
- **String inteira**: `"1"`

**Conversão Interna:**
- `0.0001 ETH` → `100000000000000 Wei` (armazenado como inteiro)
- Usa biblioteca `Decimal` para cálculos seguros de precisão
- Sem problemas de precisão de ponto flutuante

**Resposta:**
```json
{
  "hash": "0x123...",
  "status": "pending",
  "effective_fee": 0.001234,
  "created_at": "2023-12-01T10:00:00Z"
}
```

**Nota**: Todos os valores de taxa nas respostas são retornados em formato decimal ETH para consistência.

#### Validar Transação
```http
GET /v1/transaction/{tx_hash}?require_confirmations=true&min_confirmations=6
```

**Resposta:**
```json
{
  "is_valid": true,
  "transfers": [
    {
      "asset": "eth",
      "address_from": "0x742d35Cc...",
      "value": "1.0"
    }
  ],
  "confirmations": 12,
  "is_confirmed": true,
  "min_confirmations_required": 6
}
```

**Nota**: Todos os valores de transferência são retornados em formato decimal ETH (convertidos de Wei).

## Configuração e Instalação

### Pré-requisitos
- Python 3.11+
- Docker & Docker Compose
- Git

### Passo 1: Clonar Repositório
```bash
git clone <repository-url>
cd api-blockchain-python
```

### Passo 2: Configuração do Ambiente
Configure as variáveis de ambiente no `docker-compose.yml`. As principais configurações que você pode querer personalizar estão no serviço `api`:

```yaml
api:
  build: .
  container_name: blockchain-api
  environment:
    - POSTGRES_DSN=postgresql://user:password@postgres:5432/custody
    - VAULT_URL=http://vault:8200
    - VAULT_TOKEN=root
    - VAULT_SECRET_PATH=eth_wallets
    - WEB3_PROVIDER_URL=https://sepolia.infura.io/v3/SEU_PROJECT_ID  # Atualize isto
    - LOG_LEVEL=INFO
    - ENVIRONMENT=development
    - APP_VERSION=1.0.0
    - ENABLE_METRICS=true
```

**Importante**: Atualize a `WEB3_PROVIDER_URL` com seu próprio Project ID do Infura ou URL do provedor blockchain.

### Passo 3: Iniciar Todos os Serviços via Docker Compose
```bash
# Iniciar toda a infraestrutura (PostgreSQL, Vault, API, Prometheus, Grafana)
docker-compose up -d

# Verificar se todos os serviços estão rodando
docker-compose ps

# Ver logs da aplicação (opcional)
docker-compose logs -f blockchain-api
```

### Passo 4: Configuração do Banco de Dados
```bash
# Executar migrações automaticamente via Docker
docker exec blockchain-api alembic upgrade head
```

### Passo 5: Acessar a Aplicação
A aplicação estará disponível em:
- **API**: `http://localhost:8000`
- **Documentação Interativa**: `http://localhost:8000/docs`
- **Grafana** (monitoramento): `http://localhost:3000` (admin/admin)
- **Prometheus** (métricas): `http://localhost:9090`

## Testes

### Executar Testes
```bash
# Instalar dependências de teste
pip install pytest pytest-asyncio pytest-cov

# Executar testes com cobertura
export PYTHONPATH=.
pytest --cov=app --cov-report=term-missing
```

### Cobertura de Testes
O projeto mantém **98% de cobertura de testes** em todos os componentes críticos:

**Cobertura Detalhada por Módulo:**
- **Camada de Aplicação (Casos de Uso)**: 96% cobertura
  - Casos de Uso de Transação: 98% cobertura (212/212 linhas)
  - Casos de Uso de Carteira: 93% cobertura (50/54 linhas)
- **Camada de Domínio**: 86% cobertura
  - Entidades de Transação: 100% cobertura (18/18 linhas)
  - Entidades de Carteira: 100% cobertura (8/8 linhas)
  - Interfaces de Repository: 73-77% cobertura (interfaces abstratas)
- **Camada de Infraestrutura**: 98% cobertura
  - Repositories de Banco de Dados: 100% cobertura (189/189 linhas)
  - Integração Blockchain: 97% cobertura (62/64 linhas)
- **Componentes Compartilhados**: 99% cobertura
  - Monitoramento e Métricas: 98% cobertura (137/140 linhas)
  - Utilitários e Validadores: 100% cobertura (34/34 linhas)
  - Logging: 100% cobertura (43/43 linhas)

**Total: 845 linhas cobertas de 866 linhas totais (98% cobertura)**

A suíte de testes inclui:
- **253 casos de teste** cobrindo todos os caminhos críticos
- **Testes unitários** para toda lógica de negócio
- **Testes de integração** para operações de banco de dados
- **Testes com mocks** para serviços externos (Vault, Web3)
- **Testes de cenários de erro** para tratamento robusto de erros

## Considerações de Segurança

### Gerenciamento de Chaves Privadas
- **Nunca armazenar chaves privadas no banco de dados**
- **Usar HashiCorp Vault** para todos os dados sensíveis
- **Rotacionar tokens do Vault** regularmente
- **Auditar logs de acesso** do Vault

### Segurança de Transações
- **Validar todas as entradas** rigorosamente
- **Usar confirmações de transação** para prevenir ataques de reorganização
- **Implementar rate limiting** em produção
- **Monitorar preços de gas** para otimização de taxas

### Segurança de Rede
- **Usar HTTPS** em produção
- **Implementar autenticação de API** (JWT recomendado)
- **Rate limit nos endpoints** para prevenir abuso
- **Monitorar padrões suspeitos**

## Deploy

### Passo 1: Configuração do Ambiente
Criar arquivo `.env` para produção:
```env
# Banco de Dados (Produção)
POSTGRES_DSN=postgresql://user:senha_segura@prod-db:5432/custody_prod

# Vault (Produção)
VAULT_URL=https://vault.suaempresa.com
VAULT_TOKEN=<token-producao>

# Blockchain (Produção)
WEB3_PROVIDER_URL=https://mainnet.infura.io/v3/SEU_PROJECT_ID_PRODUCAO

# Monitoramento (Produção)
LOG_LEVEL=INFO
ENVIRONMENT=production
APP_VERSION=1.0.0
ENABLE_METRICS=true
```

### Passo 2: Iniciar Todos os Serviços
```bash
# Iniciar todos os serviços (PostgreSQL, Vault, API, Prometheus, Grafana, Loki)
# Nota: Devido às dependências, iniciar prometheus/grafana também iniciará a API
docker-compose up -d

# Ou iniciar serviços específicos (isso também iniciará a API devido às dependências)
docker-compose up -d postgres vault prometheus grafana

# Aguardar os serviços ficarem saudáveis
docker-compose ps
```

### Passo 3: Executar Migrações do Banco de Dados
```bash
# Executar migrações para criar/atualizar schema do banco
docker exec blockchain-api alembic upgrade head
```

### Passo 5: Verificar Deploy
```bash
# Verificar saúde da API
curl http://localhost:8000/health

# Verificar endpoint de métricas
curl http://localhost:8000/metrics

# Testar endpoints da API
curl http://localhost:8000/docs

# Verificar serviços de monitoramento
curl http://localhost:9090  # Prometheus
curl http://localhost:3000  # Grafana (admin/admin)
```

**Notas Importantes**:
- O docker-compose tem dependências entre serviços: `prometheus` depende da `api`, e `grafana` depende do `prometheus`
- Executar `docker-compose up -d prometheus grafana` automaticamente iniciará a API devido a essas dependências
- Sempre execute as migrações do banco após iniciar a infraestrutura, mas antes de usar os endpoints da API

## Monitoramento e Observabilidade

Este projeto inclui um stack completo de monitoramento e observabilidade com **Prometheus**, **Grafana** e **logging estruturado**.

### Início Rápido do Monitoramento

**Desenvolvimento com monitoramento:**
```bash
# Configurar variáveis de ambiente de monitoramento
export LOG_LEVEL=INFO
export ENABLE_METRICS=true
export ENVIRONMENT=development


# Acessar serviços de monitoramento
# API: http://localhost:8000
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin/admin)
```

### Endpoints de Monitoramento Disponíveis

- **Health Check**: `GET /health`
- **Métricas Prometheus**: `GET /metrics`
- **Documentação da API**: `GET /docs`
- **Informações Raiz**: `GET /`

### Principais Métricas Rastreadas

**Performance da API:**
- Taxa de requests e tempos de resposta
- Taxa de erros por endpoint
- Distribuição de códigos de status HTTP

**Operações Blockchain:**
- Taxa de criação/validação de transações
- Rastreamento de confirmações
- Tempos de resposta do provedor Web3
- Análise de taxas de gas

**Segurança e Infraestrutura:**
- Taxa de sucesso/falha das operações do Vault
- Performance de queries do banco de dados
- Uso do pool de conexões
- Taxa de criação de carteiras

**Métricas de Negócio:**
- Volume de transações por asset (ETH/tokens)
- Valor de transações processadas
- Taxas de sucesso/falha

### Dashboards Grafana

Dashboards pré-configurados incluem:
- **Visão Geral da API**: Taxa de requests, tempos de resposta, taxa de erros
- **Analytics de Transações**: Volume, valor, taxas de sucesso por asset
- **Saúde da Infraestrutura**: Banco de dados, Vault, conectividade blockchain
- **Monitoramento de Segurança**: Padrões de erro, atividade suspeita

### Logging Estruturado

Todos os logs são JSON estruturado com contexto rico:

```json
{
  "timestamp": "2023-12-01T10:00:00.000Z",
  "level": "INFO",
  "message": "Transação criada com sucesso",
  "tx_hash": "0x123...",
  "asset": "ETH",
  "value": 1.5,
  "duration": 0.234,
  "event": "transaction_creation"
}
```

### Alertas Recomendados

**Críticos:**
- Taxa de erro da API > 1%
- Falhas nas operações do Vault
- Problemas de conexão com banco de dados
- Downtime da aplicação

**Aviso:**
- Tempo de resposta > 2s (percentil 95)
- Alta contagem de transações pendentes
- Operações blockchain lentas

**Componentes do Stack de Monitoramento:**
- **Prometheus** - Coleta e armazenamento de métricas
- **Grafana** - Visualização e dashboards
- **Structlog + Loguru** - Logging JSON estruturado
- **FastAPI Instrumentator** - Métricas automáticas da API

## Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo LICENSE para detalhes.