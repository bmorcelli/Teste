import os
import requests
import json
import time
import random

all_device_firmware = "./test/all_device_firmware.json"
all_device_firmware_old = "./test/all_device_firmware.old.json"
temp_bin = "./test/temp.bin"
temp_folder = "./test/"

# all_device_firmware = "./script/all_device_firmware.json"
# all_device_firmware_old = "./script/all_device_firmware.old.json"
# temp_bin = "./script/temp.bin"
# temp_folder = "./script/"

# Passo 1: Renomear arquivo existente
if os.path.exists(all_device_firmware):
    os.rename(all_device_firmware, all_device_firmware_old)

# Passo 2: Download dos dados da API
url = "https://m5burner-api.m5stack.com/api/firmware"
response = requests.get(url)
data = response.json()
files_added = 0

with open(all_device_firmware, 'w') as new_file:
    json.dump(data, new_file)

# Manter apenas a última versão para os com "UIFlow" no nome
for item in data:
    if 'UIFlow' in item['name']:
        # Ordenar as versões pela data de publicação e pegar a última
        if item['versions']:
            last_version = sorted(item['versions'], key=lambda v: v['published_at'], reverse=True)[0]
            item['versions'] = [last_version]

# Filtrando versões que não terminam com '.bin'
for item in data:
    item['versions'] = [version for version in item['versions'] if version['file'].endswith('.bin') or version['file'].endswith('file')]

# Filtrar para excluir elementos sem versões ou sem arquivos binarios
data = [item for item in data if 'versions' in item and len(item['versions']) > 0]

# Corrigir espaços no início dos nomes e ordenar pelo campo 'name'
for item in data:
    item['name'] = item['name'].strip()
    
# Ordena por "name"
data = sorted(data, key=lambda x: x['name'])

# Carregando dados antigos, se disponíveis
old_data = []
if os.path.exists(all_device_firmware_old):
    with open(all_device_firmware_old, 'r') as old_file:
        old_data = json.load(old_file)
    # Passo 3: Comparação e atualização de dados
    for new_item in data:
        for old_item in old_data:
            if new_item['_id'] == old_item['_id']:
                for new_version in new_item['versions']:
                    new_version.pop('change_log', None)
                    new_version.pop('published', None)
                    for old_version in old_item['versions']:
                        if new_version['version'] == old_version['version']:
                            if new_version['file'] == old_version['file']:
                                fields_to_copy = ['Fs', 'as', 'ss', 'so', 's', 'nb', 'fs', 'fo', 'f']
                                for field in fields_to_copy:
                                    if field in old_version:
                                        new_version[field] = old_version[field]

# Passo 4: Atualizações adicionais com base em downloads parciais e leitura de bytes
for item in data:
    for version in item['versions']:
        if 's' in version:
            print(f"{item['name']} - {version['version']} - Ok ", flush=True)
        else:
            print(f"{item['name']} - {version['version']} - {version['file']}", flush=True)
            files_added+=1
            file_url = f"https://m5burner.oss-cn-shenzhen.aliyuncs.com/firmware/{version['file']}"
            time.sleep(random.uniform(0.1, 0.3))  # Pausa aleatória entre 0.1s a 0.2s
            with requests.get(file_url, stream=True) as r:
                version['Fs'] = int(r.headers.get('Content-Length', 0)) # File Size
                first_bytes = r.raw.read(33600)
                with open(temp_bin, "wb") as temp_file:
                    temp_file.write(first_bytes)

            # Leitura e cálculos
            version['s'] = False # Spiffs
            version['f'] = False # FAT Vfs
            if os.path.getsize(temp_bin) > (33120): # 0x8160 and  i = 9
                with open(temp_bin, "rb") as temp_file:
                    temp_file.seek(0x8000)
                    app_size_bytes = temp_file.read(16)
                    if (app_size_bytes[0] == 0xAA and app_size_bytes[1] == 0x50 and app_size_bytes[2] == 0x01):
                        j=0
                        for i in range(8):
                            temp_file.seek(0x8000 + i*0x20)
                            app_size_bytes = temp_file.read(16)
                            if (app_size_bytes[3] == 0x00 or app_size_bytes[3] == 0x20 or app_size_bytes[3]== 0x10) and app_size_bytes[6] == 0x01:  # confirmar valores e posiçoes, mas essa é a ideia
                                if (app_size_bytes[0x0A] << 16 | app_size_bytes[0x0B] << 8 | 0x00) > (int(r.headers.get('Content-Length', 0)) - 0x10000):
                                    version['as'] = int(r.headers.get('Content-Length', 0)) - 0x10000
                                else:
                                    version['as'] = app_size_bytes[0x0A] << 16 | app_size_bytes[0x0B] << 8 | 0x00
                            elif app_size_bytes[3] == 0x82:
                                version['ss'] = app_size_bytes[0x0A] << 16 | app_size_bytes[0x0B] << 8 | 0x00                    # Spiffs_size
                                version['so'] = app_size_bytes[0x06] << 16 | app_size_bytes[0x07] << 8 | app_size_bytes[0x08]    # Spiffs_offset
                                version['s'] = version['Fs'] >= version['so'] + version['ss']                                    # Spiffs exists or not
                            elif app_size_bytes[3] == 0x81 and j==0:
                                version['fs'] = app_size_bytes[0x0A] << 16 | app_size_bytes[0x0B] << 8 | 0x00                    # Spiffs_size
                                version['fo'] = app_size_bytes[0x06] << 16 | app_size_bytes[0x07] << 8 | app_size_bytes[0x08]    # Spiffs_offset
                                version['f'] = version['Fs'] >= version['fo'] + version['fs']                                  # Spiffs exists or not
                                j=1
                            elif app_size_bytes[3] == 0x81 and j==1:
                                version['fs2'] = app_size_bytes[0x0A] << 16 | app_size_bytes[0x0B] << 8 | 0x00                    # FAT_size
                                version['fo2'] = app_size_bytes[0x06] << 16 | app_size_bytes[0x07] << 8 | app_size_bytes[0x08]    # FAT_offset
                                version['f2'] = version['Fs'] >= version['fo2'] + version['fs2']                                  # FAT exists or not
                                j=2
                    else:
                        version['as'] = int(r.headers.get('Content-Length', 0))
                        version['nb'] = True # nb stands for No-Bootloader, to be downloaded whole


if os.path.exists(temp_bin):
    os.remove(temp_bin)  # Passo 5: Exclusão do arquivo temporário

with open(all_device_firmware, 'w') as final_file:
    json.dump(data, final_file)

# Função para filtrar e criar arquivos específicos
def create_filtered_file(category_name):
    filtered_data = [item for item in data if item['category'] == category_name]
    for item in filtered_data:
        item['versions'] = sorted(
            item.get('versions', []),
            key=lambda v: v.get('published_at', '0000-00-00'),
            reverse=True
        )
        item.pop('description', None)
        item.pop('fid', None)
        item.pop('cover', None)
        item.pop('tags', None)
        item.pop('github', None)
        item.pop('download', None)
        item.pop('published', None)
        item.pop('change_log', None)
        item.pop('_id', None)

       

    with open(f"{temp_folder}{category_name}.json", 'w') as file:
        json.dump(filtered_data, file)

# Criação dos arquivos filtrados
# create_filtered_file("cardputer")
create_filtered_file("stickc")
create_filtered_file("core2 & tough")

# Exclui os elementos 'category'
def replace_text_in_file(category_name):
    # Abrir o arquivo para leitura
    with open(f"{temp_folder}{category_name}.json", 'r') as file:
        content = file.read()
    
    # Substituir o texto especificado
    content = content.replace(f'"category": "{category_name}", ', '')
    
    # Abrir o arquivo para escrita e salvar o conteúdo modificado
    with open(f"{temp_folder}{category_name}.json", 'w') as file:
        file.write(content)

# Exemplo de uso da função
# replace_text_in_file("cardputer")
replace_text_in_file("stickc")
replace_text_in_file("core2 & tough")


print(f"\n\n\nNúmero de arquivos adicionados {files_added}\n\n\n", flush=True)
