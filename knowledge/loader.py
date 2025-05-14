from .base import PDFKnowledgeBase, KnowledgeBaseConfig
from pathlib import Path
import shutil
from logger.logger import log_info, log_debug, log_error

class KnowledgeLoader:
    def __init__(self, config: KnowledgeBaseConfig):
        self.config = config
        self.knowledge_base = PDFKnowledgeBase(config)
        
    def load_from_folder(self, folder_path: str):
        """Load PDF documents from folder into knowledge base"""
        try:
            folder = Path(folder_path)
            if not folder.exists():
                log_error(f"Folder {folder_path} not found")
                raise FileNotFoundError(f"Folder {folder_path} not found")
                
            pdf_files = list(folder.glob("*.pdf"))
            documents = []
            
            for pdf in pdf_files:
                with open(pdf, "rb") as f:
                    content = f.read()
                    documents.append({
                        "content": content,
                        "metadata": {"source": str(pdf)}
                    })
                    log_debug("Document added",{
                        "content": content,
                        "metadata": {"source": str(pdf)}
                    })
            
            return self.knowledge_base.load_documents(documents)
        except Exception as e:
            log_error(f"Knowledge load error: {str(e)}")
            return False