"""
Data Management Module - Handles loading and saving portfolio data
Unified database layer using SQLAlchemy with backward compatibility for JSON
"""

import json
import os
from flask import current_app
from datetime import datetime
from extensions import db
from models import (
    Workspace, User, Project, Skill, Client, Message,
    VisitorLog, Service, NotificationSettings
)


def get_workspace_by_username(username):
    """Get workspace by username slug"""
    return Workspace.query.filter_by(slug=username).first()


def get_or_create_workspace(username, name=None):
    """Get or create workspace for a user"""
    workspace = get_workspace_by_username(username)
    if not workspace:
        workspace = Workspace(
            name=name or username,
            slug=username,
            description='',
            plan='pro'
        )
        db.session.add(workspace)
        db.session.commit()
    return workspace


def load_data(username=None):
    """
    Load portfolio data for a specific user or global data
    Uses database first, falls back to JSON for backward compatibility
    """
    try:
        if username:
            workspace = get_workspace_by_username(username)
            if workspace:
                return workspace_to_dict(workspace)
            else:
                json_data = load_data_from_json(username=username)
                if json_data and json_data.get('username'):
                    workspace = get_or_create_workspace(username, json_data.get('name', username))
                    save_data(json_data, username=username)
                    return workspace_to_dict(workspace)
                else:
                    return load_data_from_json(username=username)
        
        users = User.query.all()
        workspaces = Workspace.query.all()
        portfolios = {}
        for ws in workspaces:
            portfolios[ws.slug] = {
                'name': ws.name,
                'title': ws.title or '',
                'description': ws.description or '',
                'about': ws.about or '',
                'photo': ws.photo or '',
                'username': ws.slug,
                'is_verified': False
            }
        return {'users': [user_to_dict(u) for u in users], 'portfolios': portfolios}
    except Exception as e:
        current_app.logger.error(f"Error loading data: {str(e)}")
        return load_data_from_json(username=username)


def workspace_to_dict(workspace):
    """Convert workspace model to dictionary"""
    if not workspace:
        return get_default_portfolio_data()
    
    skills = [{'name': s.name, 'level': s.level} for s in Skill.query.filter_by(workspace_id=workspace.id).all()]
    projects = [project_to_dict(p) for p in Project.query.filter_by(workspace_id=workspace.id).all()]
    clients = [client_to_dict(c) for c in Client.query.filter_by(workspace_id=workspace.id).all()]
    messages = [message_to_dict(m) for m in Message.query.filter_by(workspace_id=workspace.id).all()]
    services = [service_to_dict(s) for s in Service.query.filter_by(workspace_id=workspace.id).all()]
    
    visitor_logs = VisitorLog.query.filter_by(workspace_id=workspace.id).all()
    today_visits = []
    unique_ips = set()
    for log in visitor_logs:
        if log.created_at.date() == datetime.utcnow().date():
            today_visits.append({
                'ip': log.ip_address,
                'timestamp': log.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'date': log.created_at.strftime('%Y-%m-%d')
            })
        unique_ips.add(log.ip_address)
    
    notifications = {}
    notif_settings = NotificationSettings.query.filter_by(workspace_id=workspace.id).first()
    if notif_settings and notif_settings.telegram_bot_token:
        notifications['telegram'] = {
            'bot_token': notif_settings.telegram_bot_token,
            'chat_id': notif_settings.telegram_chat_id,
            'configured_at': notif_settings.telegram_configured_at.strftime('%Y-%m-%d %H:%M:%S') if notif_settings.telegram_configured_at else None
        }
    
    return {
        'username': workspace.slug,
        'name': workspace.name,
        'title': workspace.title or '',
        'description': workspace.description or '',
        'about': workspace.about or '',
        'photo': workspace.photo or '',
        'skills': skills,
        'projects': projects,
        'clients': clients,
        'messages': messages,
        'services': services,
        'contact': workspace.contact or {},
        'social': workspace.social or {},
        'settings': workspace.settings or {'theme': 'luxury-gold'},
        'visitors': {'total': len(visitor_logs), 'today': today_visits, 'unique_ips': list(unique_ips)},
        'notifications': notifications
    }


def project_to_dict(project):
    result = {
        'id': project.id,
        'title': project.title,
        'description': project.description or '',
        'short_description': project.short_description or '',
        'content': project.content or '',
        'image': project.image or '',
        'demo_url': project.demo_url or '',
        'github_url': project.github_url or '',
        'technologies': project.technologies or [],
        'gallery': project.gallery or [],
        'skill_related': project.skill_related or [],
        'project_type': project.project_type or 'portfolio',
        'badge': project.badge or '',
        'created_at': project.created_at.strftime('%Y-%m-%d %H:%M:%S') if project.created_at else None
    }
    if project.project_type == 'request':
        result.update({
            'request_budget_min': project.request_budget_min,
            'request_budget_max': project.request_budget_max,
            'request_deadline': project.request_deadline.strftime('%Y-%m-%d') if project.request_deadline else None,
            'request_status': project.request_status or 'open'
        })
    return result


def client_to_dict(client):
    return {
        'id': client.id,
        'name': client.name,
        'email': client.email or '',
        'phone': client.phone or '',
        'company': client.company or '',
        'project_title': client.project_title or '',
        'project_description': client.project_description or '',
        'status': client.status or 'lead',
        'price': client.price or '',
        'deadline': client.deadline.strftime('%Y-%m-%d') if client.deadline else None,
        'start_date': client.start_date.strftime('%Y-%m-%d') if client.start_date else None,
        'notes': client.notes or '',
        'created_at': client.created_at.strftime('%Y-%m-%d %H:%M:%S') if client.created_at else None,
        'status_updated_at': client.status_updated_at.strftime('%Y-%m-%d %H:%M:%S') if client.status_updated_at else None
    }


def message_to_dict(message):
    return {
        'id': message.id,
        'name': message.name,
        'email': message.email,
        'message': message.message,
        'read': message.is_read,
        'category': message.category or 'portfolio',
        'sender_id': message.sender_id,
        'receiver_id': message.receiver_id,
        'date': message.created_at.strftime('%Y-%m-%d %H:%M:%S') if message.created_at else None
    }


def service_to_dict(service):
    return {
        'id': service.id,
        'title': service.title,
        'description': service.description or '',
        'short_description': service.short_description or '',
        'category': service.category or '',
        'pricing_type': service.pricing_type or 'custom',
        'price_min': service.price_min,
        'price_max': service.price_max,
        'currency': service.currency or 'USD',
        'deliverables': service.deliverables or [],
        'duration': service.duration or '',
        'skills_required': service.skills_required or [],
        'image': service.image or '',
        'gallery': service.gallery or [],
        'is_active': service.is_active,
        'is_featured': service.is_featured,
        'created_at': service.created_at.isoformat() if service.created_at else None,
        'updated_at': service.updated_at.isoformat() if service.updated_at else None
    }


def user_to_dict(user):
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'password_hash': user.password_hash,
        'role': user.role,
        'is_demo': user.is_demo,
        'is_verified': user.is_verified,
        'must_change_password': user.must_change_password,
        'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else None
    }


def get_default_portfolio_data():
    return {
        'name': '',
        'title': 'Web Developer & Designer',
        'description': 'Welcome to my professional portfolio.',
        'skills': [], 'projects': [], 'services': [], 'messages': [], 'clients': [],
        'settings': {'theme': 'luxury-gold'},
        'visitors': {'total': 0, 'today': [], 'unique_ips': []}
    }


def save_data(user_data, username=None, auto_backup=True):
    try:
        if not username:
            if os.environ.get('FLASK_ENV') == 'production':
                return False
            return save_data_to_json(user_data, username, auto_backup)
        
        workspace = get_or_create_workspace(username, user_data.get('name'))
        workspace.name = user_data.get('name', workspace.name)
        workspace.title = user_data.get('title', '')
        workspace.description = user_data.get('description', '')
        workspace.photo = user_data.get('photo', '')
        workspace.about = user_data.get('about', '')
        workspace.contact = user_data.get('contact', {})
        workspace.social = user_data.get('social', {})
        workspace.settings = user_data.get('settings', {'theme': 'luxury-gold'})
        
        if 'skills' in user_data:
            Skill.query.filter_by(workspace_id=workspace.id).delete()
            for skill_data in user_data.get('skills', []):
                skill = Skill(workspace_id=workspace.id, name=skill_data.get('name', ''), level=skill_data.get('level', 50))
                db.session.add(skill)
        
        if 'projects' in user_data:
            Project.query.filter_by(workspace_id=workspace.id).delete()
            for project_data in user_data.get('projects', []):
                request_deadline = None
                if project_data.get('request_deadline'):
                    try:
                        request_deadline = datetime.strptime(project_data['request_deadline'], '%Y-%m-%d').date()
                    except: pass
                project = Project(
                    workspace_id=workspace.id,
                    id=project_data.get('id'),
                    title=project_data.get('title', ''),
                    description=project_data.get('description', ''),
                    short_description=project_data.get('short_description', ''),
                    content=project_data.get('content', ''),
                    image=project_data.get('image', ''),
                    demo_url=project_data.get('demo_url', ''),
                    github_url=project_data.get('github_url', ''),
                    technologies=project_data.get('technologies', []),
                    gallery=project_data.get('gallery', []),
                    skill_related=project_data.get('skill_related', []),
                    project_type=project_data.get('project_type', 'portfolio'),
                    badge=project_data.get('badge', ''),
                    request_budget_min=project_data.get('request_budget_min'),
                    request_budget_max=project_data.get('request_budget_max'),
                    request_deadline=request_deadline,
                    request_status=project_data.get('request_status', 'open')
                )
                db.session.add(project)
        
        if 'services' in user_data:
            Service.query.filter_by(workspace_id=workspace.id).delete()
            for service_data in user_data.get('services', []):
                service = Service(
                    workspace_id=workspace.id,
                    id=service_data.get('id'),
                    title=service_data.get('title', ''),
                    description=service_data.get('description', ''),
                    short_description=service_data.get('short_description', ''),
                    category=service_data.get('category', ''),
                    pricing_type=service_data.get('pricing_type', 'custom'),
                    price_min=service_data.get('price_min'),
                    price_max=service_data.get('price_max'),
                    currency=service_data.get('currency', 'USD'),
                    deliverables=service_data.get('deliverables', []),
                    duration=service_data.get('duration', ''),
                    skills_required=service_data.get('skills_required', []),
                    image=service_data.get('image', ''),
                    gallery=service_data.get('gallery', []),
                    is_active=service_data.get('is_active', True),
                    is_featured=service_data.get('is_featured', False)
                )
                db.session.add(service)
        
        if 'clients' in user_data:
            Client.query.filter_by(workspace_id=workspace.id).delete()
            for client_data in user_data.get('clients', []):
                deadline = None
                start_date = None
                if client_data.get('deadline'):
                    try: deadline = datetime.strptime(client_data['deadline'], '%Y-%m-%d').date()
                    except: pass
                if client_data.get('start_date'):
                    try: start_date = datetime.strptime(client_data['start_date'], '%Y-%m-%d').date()
                    except: pass
                client = Client(
                    workspace_id=workspace.id,
                    id=client_data.get('id'),
                    name=client_data.get('name', ''),
                    email=client_data.get('email', ''),
                    phone=client_data.get('phone', ''),
                    company=client_data.get('company', ''),
                    project_title=client_data.get('project_title', ''),
                    project_description=client_data.get('project_description', ''),
                    status=client_data.get('status', 'lead'),
                    price=client_data.get('price', ''),
                    deadline=deadline,
                    start_date=start_date,
                    notes=client_data.get('notes', '')
                )
                db.session.add(client)
        
        db.session.commit()
        if os.environ.get('FLASK_ENV') != 'production':
            save_data_to_json(user_data, username, auto_backup)
        return True
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error saving data: {str(e)}")
        if os.environ.get('FLASK_ENV') == 'production': return False
        return save_data_to_json(user_data, username, auto_backup)


def load_data_from_json(username=None):
    try:
        if os.environ.get('FLASK_ENV') == 'production': return get_default_portfolio_data() if username else {}
        data = {}
        if os.path.exists('data.json'):
            with open('data.json', 'r', encoding='utf-8') as file:
                data = json.load(file)
        if username:
            return data.get('portfolios', {}).get(username, get_default_portfolio_data())
        return data
    except: return {}


def save_data_to_json(user_data, username=None, auto_backup=True):
    try:
        if os.environ.get('FLASK_ENV') == 'production': return True
        all_data = load_data_from_json()
        if username:
            if 'portfolios' not in all_data: all_data['portfolios'] = {}
            all_data['portfolios'][username] = user_data
        else: all_data.update(user_data)
        with open('data.json', 'w', encoding='utf-8') as file:
            json.dump(all_data, file, ensure_ascii=False, indent=2)
    except: pass


def get_current_theme(session_obj):
    username = session_obj.get('username')
    if not username: return 'luxury-gold'
    user_data = load_data(username=username)
    return user_data.get('settings', {}).get('theme', 'luxury-gold')


def get_global_meta():
    return {
        'title': 'Codexx Academy | Elite Proof-of-Work Ecosystem',
        'description': 'The premier ecosystem for verified professionals.',
        'keywords': 'Codexx Academy, Proof of Work'
    }
