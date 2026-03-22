import re
from PyQt6.QtWidgets import QTableWidgetItem

def parse_val_brl(raw):
    """
    Converte uma string de moeda (ex: 'R$ 1.234,56') para float.
    """
    if raw is None: return 0.0
    s = str(raw).strip().replace("R$", "")
    s = re.sub(r"[^0-9,.\-]", "", s)
    if s.count(",") > 0 and s.count(".") > 0:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except:
        return 0.0

def fmt_brl(v):
    """Formata um float para o padrão 'R$ XX.XXX,XX'."""
    s = f"{v:,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")

class NumericTableWidgetItem(QTableWidgetItem):
    """
    Item de tabela personalizado que ordena baseando-se no valor numérico,
    mas exibe o texto formatado.
    """
    def __lt__(self, other):
        # Tenta obter o valor armazenado em UserRole (o float real)
        val1 = self.data(0x0100) # Qt.ItemDataRole.UserRole
        val2 = other.data(0x0100)
        
        # Se ambos forem números, compara como números
        if isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
            return val1 < val2
            
        # Fallback para ordenação de texto padrão
        return super().__lt__(other)