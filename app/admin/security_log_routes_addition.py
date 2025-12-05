

# ==================== Security Logs ====================

@bp.route('/security-logs')
@login_required
@admin_required
def security_logs():
    """View security logs with filtering."""
    page = request.args.get('page', 1, type=int)
    per_page = 50

    # Filtering parameters
    event_type = request.args.get('event_type')
    severity = request.args.get('severity')
    user_id = request.args.get('user_id', type=int)
    ip_address = request.args.get('ip_address')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    show_resolved = request.args.get('show_resolved', 'all')

    # Build query
    query = db.select(SecurityLog).order_by(desc(SecurityLog.created_at))

    # Apply filters
    if event_type:
        try:
            query = query.where(SecurityLog.event_type == SecurityEventType(event_type))
        except ValueError:
            pass

    if severity:
        try:
            query = query.where(SecurityLog.severity == SecurityLogSeverity(severity))
        except ValueError:
            pass

    if user_id:
        query = query.where(SecurityLog.user_id == user_id)

    if ip_address:
        query = query.where(SecurityLog.ip_address == ip_address)

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.where(SecurityLog.created_at >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.where(SecurityLog.created_at < end_dt)
        except ValueError:
            pass

    if show_resolved == 'unresolved':
        query = query.where(SecurityLog.resolved == False)
    elif show_resolved == 'resolved':
        query = query.where(SecurityLog.resolved == True)

    # Paginate
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    logs = pagination.items

    # Get statistics
    total_logs = db.session.scalar(db.select(func.count()).select_from(SecurityLog))
    unresolved_logs = db.session.scalar(
        db.select(func.count()).select_from(SecurityLog).where(SecurityLog.resolved == False)
    )

    # Get recent critical events
    critical_events = db.session.scalars(
        db.select(SecurityLog)
        .where(SecurityLog.severity == SecurityLogSeverity.CRITICAL)
        .where(SecurityLog.resolved == False)
        .order_by(desc(SecurityLog.created_at))
        .limit(10)
    ).all()

    return render_template('admin/security_logs.html',
                         title='Security Logs',
                         logs=logs,
                         pagination=pagination,
                         total_logs=total_logs,
                         unresolved_logs=unresolved_logs,
                         critical_events=critical_events,
                         event_types=SecurityEventType,
                         severity_levels=SecurityLogSeverity,
                         filters={
                             'event_type': event_type,
                             'severity': severity,
                             'user_id': user_id,
                             'ip_address': ip_address,
                             'start_date': start_date,
                             'end_date': end_date,
                             'show_resolved': show_resolved
                         })


@bp.route('/security-logs/<int:log_id>')
@login_required
@admin_required
def security_log_detail(log_id):
    """View detailed information about a specific security log."""
    log = db.session.get(SecurityLog, log_id)
    if not log:
        abort(404)

    # Get related logs (same IP address, same user, within 1 hour)
    related_logs = []
    if log.ip_address:
        related_logs = db.session.scalars(
            db.select(SecurityLog)
            .where(SecurityLog.ip_address == log.ip_address)
            .where(SecurityLog.id != log.id)
            .where(SecurityLog.created_at.between(
                log.created_at - timedelta(hours=1),
                log.created_at + timedelta(hours=1)
            ))
            .order_by(desc(SecurityLog.created_at))
            .limit(10)
        ).all()

    return render_template('admin/security_log_detail.html',
                         title=f'Security Log #{log_id}',
                         log=log,
                         related_logs=related_logs)


@bp.route('/security-logs/<int:log_id>/resolve', methods=['POST'])
@login_required
@admin_required
def resolve_security_log(log_id):
    """Mark a security log as resolved."""
    log = db.session.get(SecurityLog, log_id)
    if not log:
        abort(404)

    resolution_notes = request.form.get('resolution_notes', '').strip()

    try:
        log.resolved = True
        log.resolved_at = datetime.utcnow()
        log.resolved_by = current_user.id
        log.resolution_notes = resolution_notes
        db.session.commit()

        current_app.logger.info(f"Admin {current_user.id} resolved security log {log_id}")
        flash('Security log marked as resolved.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error resolving security log: {e}", exc_info=True)
        flash('Error resolving security log.', 'danger')

    return redirect(url_for('admin.security_log_detail', log_id=log_id))


@bp.route('/security-logs/<int:log_id>/unresolve', methods=['POST'])
@login_required
@admin_required
def unresolve_security_log(log_id):
    """Mark a security log as unresolved."""
    log = db.session.get(SecurityLog, log_id)
    if not log:
        abort(404)

    try:
        log.resolved = False
        log.resolved_at = None
        log.resolved_by = None
        log.resolution_notes = None
        db.session.commit()

        current_app.logger.info(f"Admin {current_user.id} marked security log {log_id} as unresolved")
        flash('Security log marked as unresolved.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error unresolving security log: {e}", exc_info=True)
        flash('Error unresolving security log.', 'danger')

    return redirect(url_for('admin.security_log_detail', log_id=log_id))
