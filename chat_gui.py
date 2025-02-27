import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
from datetime import datetime
import time

class ChatWindow:
    def __init__(self, client):
        self.client = client
        self.root = tk.Tk()
        self.root.title(f"Chat - {client.username}")
        self.root.geometry("800x600")
        
        # Adicionar esta linha
        self.message_var = tk.StringVar()
        
        # Criar e configurar widgets
        self.create_widgets()
        
        # Centralizar janela
        self.center_window()
        
    def create_widgets(self):
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Frame para botões (novo)
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))

        # Botão de sair
        self.quit_button = ttk.Button(buttons_frame, text="Sair", command=self.logout)
        self.quit_button.pack(side=tk.LEFT, padx=5)
        
        # Informações do usuário
        info_frame = ttk.LabelFrame(main_frame, text="Informações do Usuário", padding="5")
        info_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(info_frame, text=f"Usuário: {self.client.username}").grid(row=0, column=0, sticky=tk.W)
        
        # Frame para coordenadas
        coord_frame = ttk.Frame(info_frame)
        coord_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        self.lat_var = tk.StringVar(value=str(self.client.location[0]))
        self.lon_var = tk.StringVar(value=str(self.client.location[1]))
        
        ttk.Label(coord_frame, text="Latitude:").grid(row=0, column=0)
        self.lat_entry = ttk.Entry(coord_frame, textvariable=self.lat_var, width=15)
        self.lat_entry.grid(row=0, column=1)
        self.lat_entry.config(state='readonly')
        
        ttk.Label(coord_frame, text="Longitude:").grid(row=0, column=2, padx=(10, 0))
        self.lon_entry = ttk.Entry(coord_frame, textvariable=self.lon_var, width=15)
        self.lon_entry.grid(row=0, column=3)
        self.lon_entry.config(state='readonly')
        
        self.edit_btn = ttk.Button(coord_frame, text="Editar", command=self.toggle_edit)
        self.edit_btn.grid(row=0, column=4, padx=(10, 0))
        
        self.update_btn = ttk.Button(coord_frame, text="Atualizar", command=self.update_location, state='disabled')
        self.update_btn.grid(row=0, column=5, padx=(5, 0))
        
        # Frame para usuários próximos
        users_frame = ttk.LabelFrame(main_frame, text="Usuários Próximos", padding="5")
        users_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        
        refresh_btn = ttk.Button(users_frame, text="Atualizar Lista", command=self.refresh_users)
        refresh_btn.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.users_list = tk.Listbox(users_frame, height=10)
        self.users_list.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Frame para mensagens
        msg_frame = ttk.Frame(main_frame)
        msg_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Campo de chat
        self.chat_area = scrolledtext.ScrolledText(msg_frame, wrap=tk.WORD, height=15)
        self.chat_area.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.chat_area.config(state='disabled')
        
        # Frame para envio de mensagens
        send_frame = ttk.Frame(main_frame)
        send_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        
        ttk.Label(send_frame, text="Para:").grid(row=0, column=0, padx=(0, 5))
        self.recipient_var = tk.StringVar()
        self.recipient_entry = ttk.Entry(send_frame, textvariable=self.recipient_var, width=15)
        self.recipient_entry.grid(row=0, column=1, padx=(0, 5))
        
        ttk.Label(send_frame, text="Mensagem:").grid(row=0, column=2, padx=(5, 5))
        self.message_entry = ttk.Entry(send_frame, textvariable=self.message_var, width=40)
        self.message_entry.grid(row=0, column=3, padx=(0, 5))
        
        send_btn = ttk.Button(send_frame, text="Enviar", command=self.send_message)
        send_btn.grid(row=0, column=4)
        
        # Configurar grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        msg_frame.columnconfigure(0, weight=1)
        msg_frame.rowconfigure(0, weight=1)
        
    def toggle_edit(self):
        # current_state = self.lat_entry.cget('state')
        # if current_state == 'readonly':
        #     # Habilitar edição
        #     self.lat_entry.config(state='normal')
        #     self.lon_entry.config(state='normal')
        #     self.update_btn.config(state='normal')
        #     self.edit_btn.config(text='Cancelar')
        # else:
        #     # Desabilitar edição
        #     self.lat_entry.config(state='readonly')
        #     self.lon_entry.config(state='readonly')
        #     self.update_btn.config(state='disabled')
        #     self.edit_btn.config(text='Editar')
        #     # Restaurar valores originais
        #     self.lat_var.set(str(self.client.location[0]))
        #     self.lon_var.set(str(self.client.location[1]))
         # Verifica se o widget está no estado 'readonly'
        if 'readonly' in self.lat_entry.state():
            # Habilitar edição: removendo o estado 'readonly'
            self.lat_entry.state(['!readonly'])
            self.lon_entry.state(['!readonly'])
            self.update_btn.state(['!disabled'])
            self.edit_btn.config(text='Cancelar')
        else:
            # Desabilitar edição: definindo o estado como 'readonly'
            self.lat_entry.state(['readonly'])
            self.lon_entry.state(['readonly'])
            self.update_btn.state(['disabled'])
            self.edit_btn.config(text='Editar')
            # Restaurar valores originais
            self.lat_var.set(str(self.client.location[0]))
            self.lon_var.set(str(self.client.location[1]))
    
    def update_location(self):
        try:
            lat = float(self.lat_var.get())
            lon = float(self.lon_var.get())
            print(f"Debug - Tentando atualizar localização para: ({lat}, {lon})")
            success = self.client.update_location((lat, lon))
            if success:
                self.toggle_edit()
                self.refresh_users()
                messagebox.showinfo("Sucesso", "Localização atualizada com sucesso!")
            else:
                messagebox.showerror("Erro", "Não foi possível atualizar a localização. Verifique o console para mais detalhes.")
        except ValueError:
            messagebox.showerror("Erro", "Coordenadas inválidas. Use números decimais.")
    
    def refresh_users(self):
        self.users_list.delete(0, tk.END)
        self.client.refresh_nearby_users()
        for user in self.client.nearby_users:
            self.users_list.insert(tk.END, f"{user['username']} - {user['distance']:.2f}m")
    
    def send_message(self):
        recipient = self.recipient_var.get().strip()
        message = self.message_var.get().strip()
        
        if not recipient or not message:
            messagebox.showwarning("Aviso", "Por favor, preencha o destinatário e a mensagem")
            return
        
        # Verificar se o usuário está na lista de usuários próximos
        recipient_nearby = any(user['username'] == recipient for user in self.client.nearby_users)
        
        if not recipient_nearby:
            messagebox.showinfo("Aviso", "Usuário não está próximo. Mensagem será entregue quando estiver no alcance.")
        
        success = self.client.send_message(recipient, message)
        if success:
            self.add_message("Você", recipient, message)
            self.message_var.set("")  # Limpar campo de mensagem
        else:
            messagebox.showerror("Erro", "Não foi possível enviar a mensagem")
    
    def add_message(self, sender, recipient, message):
        self.chat_area.config(state='normal')
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.chat_area.insert(tk.END, f"[{timestamp}] {sender} para {recipient}: {message}\n")
        self.chat_area.see(tk.END)
        self.chat_area.config(state='disabled')
    
    def receive_message(self, sender, message):
        """Recebe mensagem de outro usuário"""
        # Usar o método add_message para adicionar a mensagem na interface
        self.root.after(0, lambda: self.add_message(sender, "você", message))
        return True
    
    def update_messages(self):
        """Thread para atualizar mensagens periodicamente"""
        while True:
            time.sleep(1)
            # Verificar mensagens offline
            self.root.after(0, self.client.check_offline_messages)
    
    def center_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def logout(self):
        """Realiza o logout do usuário"""
        try:
            self.client.logout()  # Novo método que vamos criar
            self.root.quit()
            self.root.destroy()
        except Exception as e:
            print(f"Erro ao fazer logout: {e}")
            self.root.destroy()
    
    def run(self):
        self.root.mainloop()