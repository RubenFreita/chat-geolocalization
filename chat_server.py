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
        
        # Configuração do RabbitMQ
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue='offline_messages')
        
        # Iniciar thread para monitorar usuários inativos
        self.monitor_thread = threading.Thread(target=self.monitor_inactive_users)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        print("Servidor de chat iniciado!")
    
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
            # Usuário não existe
            return False, "Usuário não encontrado"
        
        sender_location = self.users[sender]['location']
        recipient_location = self.users[recipient]['location']
        
        distance = self.calculate_distance(sender_location, recipient_location)
        
        if distance <= 200:
            # Usuário está próximo, pode enviar diretamente
            return True, "Mensagem enviada diretamente"
        else:
            # Usuário está longe, armazenar na fila
            self.store_offline_message(sender, recipient, message)
            return True, "Usuário fora de alcance. Mensagem armazenada para entrega posterior."
    
    def store_offline_message(self, sender, recipient, message):
        """Armazena mensagem offline no RabbitMQ"""
        message_data = {
            'sender': sender,
            'recipient': recipient,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        
        self.channel.basic_publish(
            exchange='',
            routing_key='offline_messages',
            body=json.dumps(message_data),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Mensagem persistente
            )
        )
        
        # Também armazenamos localmente para facilitar a recuperação
        if recipient not in self.offline_messages:
            self.offline_messages[recipient] = []
        
        self.offline_messages[recipient].append(message_data)
        print(f"Mensagem de {sender} para {recipient} armazenada na fila")
    
    def get_offline_messages(self, username):
        """Recupera mensagens offline para um usuário"""
        if username not in self.offline_messages:
            return []
        
        messages = self.offline_messages[username]
        # Limpar mensagens após recuperação
        self.offline_messages[username] = []
        
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