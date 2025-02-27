import tkinter as tk
from tkinter import ttk, messagebox

class LoginWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Chat com Localização - Login")
        self.root.geometry("400x300")
        
        # Variáveis para armazenar os valores
        self.username = tk.StringVar()
        self.latitude = tk.StringVar()
        self.longitude = tk.StringVar()
        self.user_data = None
        
        # Manipulador para o evento de fechamento da janela
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Criar e configurar widgets
        self.create_widgets()
        
        # Centralizar janela
        self.center_window()
        
    def create_widgets(self):
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Título
        title_label = ttk.Label(main_frame, text="Bem-vindo ao Chat", font=('Helvetica', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Username
        ttk.Label(main_frame, text="Nome de usuário:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.username).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Latitude
        ttk.Label(main_frame, text="Latitude:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.latitude).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Longitude
        ttk.Label(main_frame, text="Longitude:").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.longitude).grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # Botões
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=20)
        
        ttk.Button(btn_frame, text="Gerar Coordenadas", command=self.generate_coordinates).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Entrar", command=self.login).pack(side=tk.LEFT, padx=5)
        
        # Configurar grid
        main_frame.columnconfigure(1, weight=1)
    
    def center_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def generate_coordinates(self):
        import random
        self.latitude.set(f"{random.uniform(-23.5, -23.6):.6f}")
        self.longitude.set(f"{random.uniform(-46.6, -46.7):.6f}")
    
    def login(self):
        if not self.username.get().strip():
            messagebox.showerror("Erro", "Por favor, insira um nome de usuário")
            return
        
        try:
            lat = float(self.latitude.get() or "-23.550520")
            lon = float(self.longitude.get() or "-46.633308")
            
            self.user_data = {
                'username': self.username.get().strip(),
                'location': (lat, lon)
            }
            self.root.destroy()
            
        except ValueError:
            messagebox.showerror("Erro", "Coordenadas inválidas")
    
    def get_user_data(self):
        self.root.mainloop()
        return self.user_data

    def on_closing(self):
        self.user_data = None
        self.root.destroy()