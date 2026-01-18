"""
Helpers Module - Utility functions for common operations
"""

import os
import json
import shutil
from datetime import datetime
from flask import current_app, session
from .data import load_data


def allowed_file(filename):
    """Check if file extension is allowed"""
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def create_backup(manual=True):
    """Create a backup of data.json to backups folder"""
    try:
        if not os.path.exists('data.json'):
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f'backup_{timestamp}.json'
        backup_path = os.path.join('backups', backup_filename)

        os.makedirs('backups', exist_ok=True)

        with open('data.json', 'r', encoding='utf-8') as original:
            backup_content = original.read()
            with open(backup_path, 'w', encoding='utf-8') as backup:
                backup.write(backup_content)

        file_size = os.path.getsize(backup_path) / 1024

        backup_info = {
            'filename': backup_filename,
            'timestamp': datetime.now().isoformat(),
            'size_kb': round(file_size, 2),
            'type': 'manual' if manual else 'automatic'
        }

        save_backup_metadata(backup_info)
        keep_recent_backups(max_backups=20)

        return backup_info
    except Exception as e:
        current_app.logger.error(f"Error creating backup: {str(e)}")
        return None


def save_backup_metadata(backup_info):
    """Save backup metadata to JSON file"""
    try:
        os.makedirs('backups', exist_ok=True)
        metadata_file = 'backups/backups.json'
        backups_list = []

        if os.path.exists(metadata_file):
            with open(metadata_file, 'r', encoding='utf-8') as f:
                backups_list = json.load(f)

        backups_list.append(backup_info)

        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(backups_list, f, ensure_ascii=False, indent=2)
    except Exception as e:
        current_app.logger.error(f"Error saving backup metadata: {str(e)}")


def get_backups_list():
    """Get list of all backups with metadata"""
    try:
        metadata_file = 'backups/backups.json'
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r', encoding='utf-8') as f:
                backups = json.load(f)
                return sorted(backups, key=lambda x: x['timestamp'], reverse=True)
        return []
    except Exception as e:
        current_app.logger.error(f"Error reading backups list: {str(e)}")
        return []


def keep_recent_backups(max_backups=20):
    """Keep only the most recent backups"""
    try:
        backups = get_backups_list()
        if len(backups) > max_backups:
            to_delete = backups[max_backups:]
            for backup in to_delete:
                backup_path = os.path.join('backups', backup['filename'])
                if os.path.exists(backup_path):
                    os.remove(backup_path)

            updated_backups = backups[:max_backups]
            with open('backups/backups.json', 'w', encoding='utf-8') as f:
                json.dump(updated_backups, f, ensure_ascii=False, indent=2)
    except Exception as e:
        current_app.logger.error(f"Error cleaning old backups: {str(e)}")


def get_unread_messages_count():
    """Get count of unread messages for current user or admin"""
    try:
        from models import Message, User
        from extensions import db
        
        username = session.get('username')
        is_admin = session.get('is_admin', False)
        
        if not username:
            return 0
        
        if is_admin:
            unread_count = Message.query.filter(
                Message.is_read == False,
                db.or_(
                    Message.workspace_id.is_(None),
                    Message.receiver_id == 'admin',
                    Message.category == 'platform'
                )
            ).count()
        else:
            user = User.query.filter_by(username=username).first()
            if not user:
                return 0
            
            unread_count = Message.query.filter(
                Message.is_read == False,
                Message.workspace_id == user.workspace_id
            ).count()
        
        return unread_count
    except Exception as e:
        current_app.logger.error(f"Error getting unread messages count: {str(e)}")
        return 0


def get_visitor_count():
    """Get visitor count for current user's portfolio"""
    try:
        from models import User, VisitorLog
        username = session.get('username')
        if not username:
            return 0
        
        user = User.query.filter_by(username=username).first()
        if not user or not user.workspace_id:
            return 0
            
        return VisitorLog.query.filter_by(workspace_id=user.workspace_id).count()
    except Exception as e:
        current_app.logger.error(f"Error getting visitor count: {str(e)}")
        return 0


def get_clients_stats(username=None):
    """Get client statistics for user"""
    try:
        from models import User, Project, Skill, Client, Service, Message, VisitorLog
        from extensions import db
        
        if not username:
            username = session.get('username')
        
        if not username:
            return {'total': 0, 'active': 0, 'pending': 0, 'revenue': 0.0, 'recent': [], 'projects': 0, 'skills': 0, 'services': 0, 'messages': 0, 'visitors': 0, 'today_visitors': 0}
        
        user = User.query.filter_by(username=username).first()
        if not user or not user.workspace_id:
             return {'total': 0, 'active': 0, 'pending': 0, 'revenue': 0.0, 'recent': [], 'projects': 0, 'skills': 0, 'services': 0, 'messages': 0, 'visitors': 0, 'today_visitors': 0}

        workspace_id = user.workspace_id
        
        projects_count = Project.query.filter_by(workspace_id=workspace_id).count()
        skills_count = Skill.query.filter_by(workspace_id=workspace_id).count()
        services_count = Service.query.filter_by(workspace_id=workspace_id).count()
        messages_count = Message.query.filter_by(workspace_id=workspace_id).count()
        
        visitors_count = VisitorLog.query.filter_by(workspace_id=workspace_id).count()
        today = datetime.now().date()
        today_visitors = VisitorLog.query.filter(
            VisitorLog.workspace_id == workspace_id,
            db.func.date(VisitorLog.created_at) == today
        ).count()
        
        clients = Client.query.filter_by(workspace_id=workspace_id).all()
        total_clients = len(clients)
        active_clients = len([c for c in clients if c.status in ['in-progress', 'negotiation']])
        pending_clients = len([c for c in clients if c.status == 'lead'])
        
        total_revenue = 0.0
        for c in clients:
            price = getattr(c, 'price', '')
            if price:
                try:
                    price_clean = ''.join(ch for ch in str(price) if ch.isdigit() or ch == '.')
                    if price_clean:
                        total_revenue += float(price_clean)
                except (ValueError, TypeError):
                    pass
        
        return {
            'total': total_clients,
            'active': active_clients,
            'pending': pending_clients,
            'revenue': total_revenue,
            'recent': clients[-5:] if clients else [],
            'projects': projects_count,
            'skills': skills_count,
            'services': services_count,
            'messages': messages_count,
            'visitors': visitors_count,
            'today_visitors': today_visitors
        }
    except Exception as e:
        current_app.logger.error(f"Error getting client stats: {str(e)}")
        return {'total': 0, 'active': 0, 'pending': 0, 'revenue': 0.0, 'recent': [], 'projects': 0, 'skills': 0, 'services': 0, 'messages': 0, 'visitors': 0, 'today_visitors': 0}


def track_visitor(username=None):
    """Track visitor to user's portfolio"""
    try:
        from models import User, VisitorLog, Workspace
        from extensions import db
        from .security import get_client_ip
        
        if not username:
            username = session.get('username')
        
        if not username:
            return

        user = User.query.filter_by(username=username).first()
        if not user or not user.workspace_id:
            return

        client_ip = get_client_ip()
        new_log = VisitorLog(
            workspace_id=user.workspace_id,
            ip_address=client_ip,
            user_agent=getattr(current_app, 'user_agent', 'Unknown')
        )
        db.session.add(new_log)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Error tracking visitor: {str(e)}")


def sanitize_about(text: str) -> str:
    try:
        import re
        if not text:
            return ''
        txt = text.replace('\r\n', '\n').replace('\r', '\n')
        txt = re.sub(r'\n\s*\n+', '\n\n', txt)
        txt = txt.strip()
        txt = re.sub(r'<(script|style).*?>.*?</\1>', '', txt, flags=re.I | re.S)
        if '<' not in txt and '>' not in txt:
            from markupsafe import escape
            escaped = escape(txt).strip()
            paragraphs = [p.strip() for p in re.split(r'\n\s*\n', escaped) if p.strip()]
            paragraphs = [p.replace('\n', '<br>\n') for p in paragraphs]
            wrapped = ''.join(f'<p>{p}</p>' for p in paragraphs)
            return wrapped
        allowed_tags = ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li', 'span', 'b', 'i', 'u']
        txt = re.sub(r'</?(?!(' + '|'.join(allowed_tags) + r')\b)[^>]*>', '', txt, flags=re.I)
        def _strip_attrs(match):
            tag = match.group(1).lower()
            attrs = match.group(2) or ''
            if tag == 'span':
                m = re.search(r'class\s*=\s*"([^"]+)"', attrs)
                cls = ''
                if m:
                    cls_val = re.sub(r'[^a-zA-Z0-9_\-\s]', '', m.group(1))
                    cls = f' class="{cls_val}"'
                return f'<{tag}{cls}>'
            return f'<{tag}>'
        txt = re.sub(r'<(\w+)([^>]*)>', _strip_attrs, txt, flags=re.I)
        txt = re.sub(r'(?:(?:<br\s*/?>)\s*){2,}', '<br>\n', txt, flags=re.I)
        blocks = [b.strip() for b in re.split(r'\n\s*\n', txt) if b.strip()]
        normalized_blocks = []
        for block in blocks:
            if '<p' in block.lower():
                normalized_blocks.append(block)
            else:
                b_html = block.replace('\n', '<br>\n')
                normalized_blocks.append(f'<p>{b_html}</p>')
        txt = ''.join(normalized_blocks)
        txt = txt.strip()
        txt = re.sub(r'^(?:\s|(?:<br\s*/?>))+', '', txt, flags=re.I)
        txt = re.sub(r'(?:\s|(?:<br\s*/?>))+$', '', txt, flags=re.I)
        txt = re.sub(r'^(?:<p>\s*</p>)+', '', txt, flags=re.I)
        txt = re.sub(r'(?:<p>\s*</p>)+$', '', txt, flags=re.I)
        return txt
    except Exception as e:
        current_app.logger.error(f"Error sanitizing about text: {str(e)}")
        return ''


__all__ = [
    'allowed_file',
    'create_backup',
    'save_backup_metadata',
    'get_backups_list',
    'keep_recent_backups',
    'get_unread_messages_count',
    'get_visitor_count',
    'get_clients_stats',
    'track_visitor',
    'sanitize_about'
]
