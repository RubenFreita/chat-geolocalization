import Pyro4
import pika
import json
import threading
import time
import random
import sys
from datetime import datetime

@Pyro4.expose
class ChatClient:
    def __init__(self, username, initial_location):
        self.username = username
        self.location = tuple(float(x) for x in initial_location)  # Garantir que são floats
        self.server = Pyro4.Proxy("PYRONAME:chat.server")
        self.nearby_users = []
        self.user_proxies = {}  # {username: proxy}
        
        print(f"Debug - Iniciando cliente com localização: {self.location}")
        
        # Registrar no servidor
        try:
            self.daemon = Pyro4.Daemon()
            self.uri = self.daemon.register(self)
            success = self.server.register_user(username, self.location, str(self.uri))
            if not success:
                raise Exception("Falha ao registrar usuário")
        except Exception as e:
            print(f"Erro ao registrar cliente: {e}")
            raise e
        
        # Iniciar thread para receber chamadas remotas
        self.thread = threading.Thread(target=self.daemon.requestLoop)
        self.thread.daemon = True
        self.thread.start()
        
        # Iniciar thread para atualizar lista de usuários próximos
        self.refresh_thread = threading.Thread(target=self.periodic_refresh)
        self.refresh_thread.daemon = True
        self.refresh_thread.start()
        
        # Iniciar thread para heartbeat
        self.heartbeat_thread = threading.Thread(target=self.send_heartbeat)
        self.heartbeat_thread.daemon = True
        self.heartbeat_thread.start()
        
        print(f"Cliente {username} iniciado na posição {initial_location}")
        
        # Verificar mensagens offline ao iniciar
        self.check_offline_messages()
    
    def receive_message(self, sender, message):
        """Método remoto para receber mensagens"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{timestamp}] Mensagem de {sender}: {message}")
        return True
    
    def update_location(self, new_location):
        """Atualiza a localização do usuário"""
        self.location = new_location
        success = self.server.update_location(self.username, new_location)
        if success:
            print(f"Sua localização foi atualizada para {new_location}")
            # Atualizar lista de usuários próximos após mudar de localização
            self.refresh_nearby_users()
        else:
            print("Falha ao atualizar localização")
    
    def refresh_nearby_users(self):
        """Atualiza a lista de usuários próximos"""
        try:
            print("\nDebug - Solicitando usuários próximos do servidor...")
            self.nearby_users = self.server.get_nearby_users(self.username)
            print(f"Debug - Resposta do servidor: {self.nearby_users}")
            
            # Atualizar proxies
            new_proxies = {}
            for user in self.nearby_users:
                username = user['username']
                if username in self.user_proxies:
                    new_proxies[username] = self.user_proxies[username]
                else:
                    try:
                        proxy = Pyro4.Proxy(user['uri'])
                        new_proxies[username] = proxy
                    except Exception as e:
                        print(f"Debug - Erro ao criar proxy para {username}: {e}")
            
            self.user_proxies = new_proxies
            
            print("\nUsuários próximos:")
            if not self.nearby_users:
                print("Nenhum usuário próximo encontrado.")
            else:
                for i, user in enumerate(self.nearby_users):
                    print(f"{i+1}. {user['username']} - {user['distance']:.2f}m")
            
            self.check_offline_messages()
            
        except Exception as e:
            print(f"Erro ao atualizar lista de usuários: {e}")
            print(f"Debug - Detalhes do erro: {type(e).__name__}")
    
    def periodic_refresh(self):
        """Atualiza a lista de usuários próximos periodicamente"""
        while True:
            time.sleep(120)  # 2 minutos
            print("\nAtualizando lista de usuários próximos...")
            self.refresh_nearby_users()
    
    def send_heartbeat(self):
        """Envia heartbeat para o servidor periodicamente"""
        while True:
            time.sleep(60)  # 1 minuto
            try:
                self.server.user_heartbeat(self.username)
            except:
                print("Erro ao enviar heartbeat para o servidor")
    
    def send_message(self, recipient, message):
        """Envia mensagem para outro usuário"""
        if recipient in self.user_proxies:
            # Usuário está próximo, enviar diretamente
            try:
                proxy = self.user_proxies[recipient]
                proxy.receive_message(self.username, message)
                print(f"Mensagem enviada para {recipient}")
                return True
            except:
                print(f"Erro ao enviar mensagem diretamente. Tentando via servidor...")
        
        # Tentar enviar via servidor (que decidirá se armazena na fila ou não)
        success, msg = self.server.send_message(self.username, recipient, message)
        print(msg)
        return success
    
    def check_offline_messages(self):
        """Verifica se há mensagens offline para o usuário"""
        try:
            messages = self.server.get_offline_messages(self.username)
            if messages:
                print("\n=== Mensagens recebidas enquanto você estava fora de alcance ===")
                for msg in messages:
                    timestamp = datetime.fromisoformat(msg['timestamp']).strftime("%d/%m/%Y %H:%M:%S")
                    print(f"[{timestamp}] De {msg['sender']}: {msg['message']}")
                print("=== Fim das mensagens offline ===\n")
        except Exception as e:
            print(f"Erro ao verificar mensagens offline: {e}")

# Interface de linha de comando
def main():
    print("=== Cliente de Chat com Localização ===")
    username = input("Digite seu nome de usuário: ")
    
    # Gerar localização aleatória para simplificar
    lat = float(input("Digite sua latitude: ") or random.uniform(-23.5, -23.6))
    lng = float(input("Digite sua longitude: ") or random.uniform(-46.6, -46.7))
    
    initial_location = (lat, lng)
    client = ChatClient(username, initial_location)
    
    print("\nComandos disponíveis:")
    print("/users - Listar usuários próximos")
    print("/msg <usuário> <mensagem> - Enviar mensagem")
    print("/location <lat> <lng> - Atualizar localização")
    print("/exit - Sair do chat")
    
    while True:
        try:
            command = input("\n> ")
            
            if command == "/users":
                client.refresh_nearby_users()
            
            elif command.startswith("/msg "):
                parts = command.split(" ", 2)
                if len(parts) < 3:
                    print("Uso: /msg <usuário> <mensagem>")
                    continue
                
                recipient = parts[1]
                message = parts[2]
                client.send_message(recipient, message)
            
            elif command.startswith("/location "):
                parts = command.split()
                if len(parts) != 3:
                    print("Uso: /location <lat> <lng>")
                    continue
                
                try:
                    lat = float(parts[1])
                    lng = float(parts[2])
                    client.update_location((lat, lng))
                except ValueError:
                    print("Coordenadas inválidas")
            
            elif command == "/exit":
                print("Saindo do chat...")
                break
            
            else:
                print("Comando desconhecido. Digite /help para ver os comandos disponíveis.")
        
        except KeyboardInterrupt:
            print("\nSaindo do chat...")
            break
        except Exception as e:
            print(f"Erro: {e}")

if __name__ == "__main__":
    main()