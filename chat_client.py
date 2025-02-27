import Pyro4
import pika
import json
import threading
import time
import random
import sys
from datetime import datetime
from login_gui import LoginWindow
from chat_gui import ChatWindow

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
        try:
            # Verificar se o remetente está na lista de usuários próximos
            sender_nearby = any(user['username'] == sender for user in self.nearby_users)
            
            if not sender_nearby:
                # Se não estiver próximo, a mensagem deve ir para a fila MOM
                success, msg = self.server.send_message(sender, self.username, message)
                print(f"Mensagem de {sender} armazenada para entrega posterior")
                return True
            
            # Se estiver próximo, mostrar na interface
            if hasattr(self, 'gui'):
                self.gui.receive_message(sender, message)
                return True
            else:
                timestamp = datetime.now().strftime("%H:%M:%S")
                print(f"\n[{timestamp}] Mensagem de {sender}: {message}")
                return True
            
        except Exception as e:
            print(f"Erro ao receber mensagem: {e}")
            return False
    
    def update_location(self, new_location):
        """Atualiza a localização do usuário"""
        try:
            self.location = new_location
            success = self.server.update_location(self.username, new_location)
            if success:
                print(f"Sua localização foi atualizada para {new_location}")
                self.refresh_nearby_users()
                return True
            else:
                print("Falha ao atualizar localização")
                return False
        except Exception as e:
            print(f"Erro ao atualizar localização: {e}")
            return False
    
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
        try:
            # Verificar se o usuário está na lista de usuários próximos
            recipient_nearby = any(user['username'] == recipient for user in self.nearby_users)
            
            if not recipient_nearby:
                # Se não estiver próximo, enviar para o servidor armazenar na fila
                success, msg = self.server.send_message(self.username, recipient, message)
                print(msg)
                return success
            
            # Se estiver próximo, tentar enviar diretamente
            if recipient in self.user_proxies:
                try:
                    proxy = self.user_proxies[recipient]
                    proxy.receive_message(self.username, message)
                    print(f"Mensagem enviada para {recipient}")
                    return True
                except Exception as e:
                    print(f"Erro ao enviar mensagem diretamente: {e}")
                    return False
            
            return False
        except Exception as e:
            print(f"Erro no envio da mensagem: {e}")
            return False
    
    def check_offline_messages(self):
        """Verifica se há mensagens offline para o usuário"""
        try:
            messages = self.server.get_offline_messages(self.username)
            if messages:
                for msg in messages:
                    # Verificar se o remetente está próximo antes de mostrar a mensagem
                    sender_nearby = any(user['username'] == msg['sender'] for user in self.nearby_users)
                    
                    if sender_nearby:
                        if hasattr(self, 'gui'):
                            self.gui.add_message(msg['sender'], "você", msg['message'])
                        else:
                            timestamp = datetime.fromisoformat(msg['timestamp']).strftime("%d/%m/%Y %H:%M:%S")
                            print(f"[{timestamp}] De {msg['sender']}: {msg['message']}")
                    else:
                        # Se ainda não está próximo, devolver a mensagem para a fila
                        self.server.store_offline_message(msg['sender'], self.username, msg['message'])
                
            return True
        except Exception as e:
            print(f"Erro ao verificar mensagens offline: {e}")
            return False

# Interface de linha de comando
def main():
    # Iniciar interface gráfica de login
    login_window = LoginWindow()
    user_data = login_window.get_user_data()
    
    if not user_data:
        print("Login cancelado")
        return
    
    # Criar cliente com os dados do login
    client = ChatClient(user_data['username'], user_data['location'])
    
    # Criar e iniciar interface gráfica principal
    chat_window = ChatWindow(client)
    client.gui = chat_window
    chat_window.run()

if __name__ == "__main__":
    main()