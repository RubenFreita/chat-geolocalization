# chat_server.py
import Pyro4
import pika
import json
import time
import threading
from math import sqrt, cos, radians
from datetime import datetime

@Pyro4.expose
class ChatServer:
    def __init__(self):
        self.users = {}  # {username: {location: (lat, long), last_active: timestamp, uri: pyro_uri}}
        self.offline_messages = {}  # {recipient: [messages]}
        
        if not self.setup_rabbitmq_connection():
            raise Exception("Falha ao configurar conexão com RabbitMQ")
        
        try:
            # Fazer o binding com a nova exchange
            self.channel.queue_bind(
                exchange='chat_exchange',
                queue='offline_messages',
                routing_key='offline_messages.*'
            )
        except Exception as e:
            print(f"Erro ao fazer binding da fila: {e}")
            raise e
        
        # Iniciar consumidor de mensagens
        #self.setup_message_consumer()
        
        # Iniciar thread para monitorar usuários inativos
        self.monitor_thread = threading.Thread(target=self.monitor_inactive_users)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        print("Servidor de chat iniciado!")
    
    def setup_rabbitmq_connection(self):
        """Configura ou reconfigura a conexão com RabbitMQ"""
        try:
            # Parâmetros de conexão mais robustos
            parameters = pika.ConnectionParameters(
                host='localhost',
                heartbeat=600,
                blocked_connection_timeout=300,
                connection_attempts=3,
                retry_delay=5
            )
            
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            # Configurar prefetch para melhor distribuição de carga
            self.channel.basic_qos(prefetch_count=1)
            
            try:
                # Tentar deletar a exchange se ela existir
                self.channel.exchange_delete(exchange='chat_exchange')
            except:
                pass  # Ignora erro se a exchange não existir
            
            # Criar uma exchange própria
            self.channel.exchange_declare(
                exchange='chat_exchange',
                exchange_type='topic',
                durable=True
            )
            
            # Declarar fila padrão
            self.channel.queue_declare(
                queue='offline_messages',
                durable=True
            )
            
            print("Conexão com RabbitMQ estabelecida com sucesso")
            return True
        except Exception as e:
            print(f"Erro ao configurar RabbitMQ: {e}")
            return False
    
    def register_user(self, username, location, uri):
        """Registra um novo usuário no sistema"""
        self.users[username] = {
            'location': location,
            'last_active': time.time(),
            'uri': uri
        }
        print(f"Usuário {username} registrado na posição {location}")
        return True
    
    def update_location(self, username, new_location):
        """Atualiza a localização de um usuário"""
        if username in self.users:
            self.users[username]['location'] = new_location
            self.users[username]['last_active'] = time.time()
            print(f"Localização de {username} atualizada para {new_location}")
            return True
        return False
    
    def get_nearby_users(self, username):
        """Retorna usuários próximos (até 200m)"""
        if username not in self.users:
            print(f"Usuário {username} não encontrado no servidor")
            return []
        
        user_location = self.users[username]['location']
        nearby_users = []
        
        print(f"\nDebug - Usuário {username} na posição {user_location}")
        print("Debug - Todos os usuários:", self.users)
        
        for other_user, data in self.users.items():
            if other_user != username:
                other_location = data['location']
                try:
                    distance = self.calculate_distance(user_location, other_location)
                    print(f"Debug - Calculando distância entre {username} ({user_location}) e {other_user} ({other_location}): {distance:.2f}m")
                    
                    if distance <= 200:  # 200 metros
                        nearby_users.append({
                            'username': other_user,
                            'location': other_location,
                            'distance': distance,
                            'uri': data['uri']
                        })
                except Exception as e:
                    print(f"Erro ao calcular distância: {e}")
        
        self.users[username]['last_active'] = time.time()
        return nearby_users
    
    def calculate_distance(self, loc1, loc2):
        """Calcula a distância euclidiana entre dois pontos em metros"""
        try:
            # Convertendo coordenadas para metros (aproximadamente)
            lat_to_meters = 111320  # 1 grau de latitude ≈ 111.32 km
            lon_to_meters = 111320 * abs(cos(radians(loc1[0])))  # Ajusta longitude baseado na latitude
            
            # Calcula diferenças em metros
            lat_diff = (loc1[0] - loc2[0]) * lat_to_meters
            lon_diff = (loc1[1] - loc2[1]) * lon_to_meters
            
            distance = sqrt(lat_diff**2 + lon_diff**2)
            print(f"Debug - Distância calculada: {distance:.2f}m")
            return distance
        except Exception as e:
            print(f"Erro no cálculo de distância: {e}")
            raise e
    
    def send_message(self, sender, recipient, message):
        """Envia uma mensagem para outro usuário"""
        if recipient not in self.users:
            return False, "Usuário não encontrado"
        
        sender_location = self.users[sender]['location']
        recipient_location = self.users[recipient]['location']
        
        try:
            distance = self.calculate_distance(sender_location, recipient_location)
            
            if distance <= 200:
                # Usuário está próximo, tentar enviar diretamente
                try:
                    recipient_proxy = Pyro4.Proxy(self.users[recipient]['uri'])
                    success = recipient_proxy.receive_message(sender, message)
                    if success:
                        return True, "Mensagem enviada diretamente"
                    else:
                        # Se falhar o envio direto, armazenar na fila
                        self.store_offline_message(sender, recipient, message)
                        return True, "Falha no envio direto. Mensagem armazenada para entrega posterior."
                except Exception as e:
                    print(f"Erro ao enviar mensagem diretamente: {e}")
                    self.store_offline_message(sender, recipient, message)
                    return True, "Falha no envio direto. Mensagem armazenada para entrega posterior."
            else:
                # Usuário está longe, armazenar na fila
                self.store_offline_message(sender, recipient, message)
                return True, "Usuário fora de alcance. Mensagem armazenada para entrega posterior."
        except Exception as e:
            print(f"Erro ao enviar mensagem: {e}")
            return False, "Erro ao processar mensagem"
    
    def store_offline_message(self, sender, recipient, message):
        """Armazena mensagem offline no RabbitMQ"""
        max_retries = 3
        current_try = 0
        
        while current_try < max_retries:
            try:
                if not self.ensure_connection():
                    raise Exception("Não foi possível estabelecer conexão com RabbitMQ")
                
                message_data = {
                    'sender': sender,
                    'recipient': recipient,
                    'message': message,
                    'timestamp': datetime.now().isoformat()
                }
                print(f"Mensagem a ser armazenada: {message_data}")
                
                queue_name = f'offline_messages.{recipient}'
                
                # Declarar fila específica para o recipient
                self.channel.queue_declare(
                    queue=queue_name,
                    durable=True
                )

                # Vincular a fila ao exchange 'chat_exchange' com a routing_key adequada
                self.channel.queue_bind(
                    queue=queue_name,
                    exchange='chat_exchange',
                    routing_key=queue_name  # A routing key deve corresponder àquela utilizada na publicação
                )
                
                # Publicar mensagem
                self.channel.basic_publish(
                    exchange='chat_exchange',
                    routing_key=queue_name,
                    body=json.dumps(message_data),
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        content_type='application/json'
                    )
                )
                print(f"Mensagem publicada com sucesso para a fila {queue_name}")
                return True
                
            except Exception as e:
                print(f"Tentativa {current_try + 1} falhou: {e}")
                current_try += 1
                time.sleep(2)  # Esperar mais tempo entre tentativas
        
        print("Falha após todas as tentativas")
        return False
    
    def setup_message_consumer(self):
        """Configura o consumidor de mensagens"""
        def callback(ch, method, properties, body):
            message_data = json.loads(body)
            recipient = message_data['recipient']
            
            if recipient not in self.offline_messages:
                self.offline_messages[recipient] = []
            self.offline_messages[recipient].append(message_data)
            
            # Confirmar processamento da mensagem
            ch.basic_ack(delivery_tag=method.delivery_tag)

        self.channel.basic_consume(
            queue='offline_messages',
            on_message_callback=callback
        )
        # Iniciar thread para consumir mensagens
        threading.Thread(target=self.channel.start_consuming, daemon=True).start()
    
    def get_offline_messages(self, username):
        """Recupera mensagens offline para um usuário"""
        messages = []
        max_retries = 3
        current_try = 0
        
        while current_try < max_retries:
            try:
                if not self.ensure_connection():
                    raise Exception("Não foi possível estabelecer conexão com RabbitMQ")
                
                queue_name = f'offline_messages.{username}'
                
                # Declarar fila se não existir
                self.channel.queue_declare(
                    queue=queue_name,
                    durable=True
                )
                
                print(f"Debug - Verificando fila {queue_name} para mensagens offline")
                
                # Consumir mensagens
                while True:
                    method_frame, header_frame, body = self.channel.basic_get(
                        queue=queue_name,
                        auto_ack=False
                    )
                    
                    if not method_frame:
                        break
                    
                    try:
                        message_data = json.loads(body)
                        sender = message_data['sender']
                        
                        if sender in self.users:
                            distance = self.calculate_distance(
                                self.users[sender]['location'],
                                self.users[username]['location']
                            )
                            print(f"Debug - Verificando mensagem de {sender} para {username}. Distância: {distance:.2f}m")
                            
                            if distance <= 200:
                                messages.append(message_data)
                                self.channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                                print(f"Debug - Mensagem entregue: distância {distance:.2f}m <= 200m")
                            else:
                                print(f"Debug - Mensagem mantida na fila: distância {distance:.2f}m > 200m")
                                self.channel.basic_reject(
                                    delivery_tag=method_frame.delivery_tag,
                                    requeue=True
                                )
                                break
                        else:
                            self.channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                            
                    except Exception as e:
                        print(f"Erro ao processar mensagem: {e}")
                        self.channel.basic_reject(
                            delivery_tag=method_frame.delivery_tag,
                            requeue=True
                        )
                
                print(f"Debug - Total de mensagens encontradas: {len(messages)}")
                return messages
                
            except Exception as e:
                print(f"Tentativa {current_try + 1} falhou: {e}")
                current_try += 1
                time.sleep(2)
        
        print("Falha após todas as tentativas")
        return messages
    
    def user_heartbeat(self, username):
        """Atualiza o timestamp de atividade do usuário"""
        if username in self.users:
            self.users[username]['last_active'] = time.time()
            return True
        return False
    
    def monitor_inactive_users(self):
        """Remove usuários inativos após 5 minutos"""
        while True:
            current_time = time.time()
            inactive_users = []
            
            for username, data in self.users.items():
                if current_time - data['last_active'] > 300:  # 5 minutos
                    inactive_users.append(username)
            
            for username in inactive_users:
                print(f"Removendo usuário inativo: {username}")
                del self.users[username]
            
            time.sleep(60)  # Verificar a cada minuto
    
    def ensure_connection(self):
        """Garante que a conexão está ativa"""
        try:
            if not self.connection or not self.connection.is_open:
                print("Conexão fechada. Reconectando...")
                return self.setup_rabbitmq_connection()
            if not self.channel or not self.channel.is_open:
                print("Canal fechado. Recriando...")
                self.channel = self.connection.channel()
                self.channel.basic_qos(prefetch_count=1)
                return True
            return True
        except Exception as e:
            print(f"Erro ao verificar conexão: {e}")
            return False

# Iniciar o servidor
if __name__ == "__main__":
    # Criar e registrar o servidor no name server
    daemon = Pyro4.Daemon()
    ns = Pyro4.locateNS()
    
    server = ChatServer()
    uri = daemon.register(server)
    
    # Registrar o servidor no name server
    ns.register("chat.server", uri)
    
    print(f"Servidor de chat disponível em: {uri}")
    daemon.requestLoop()