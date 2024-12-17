import os
from pathlib import Path
from typing import Optional
import requests

from open_webui.models.functions import (
    FunctionForm,
    FunctionModel,
    FunctionResponse,
    Functions,
)
from open_webui.utils.plugin import load_function_module_by_id, replace_imports, extract_frontmatter
from open_webui.config import CACHE_DIR
from open_webui.constants import ERROR_MESSAGES
from fastapi import APIRouter, Depends, HTTPException, Request, status
from open_webui.utils.auth import get_admin_user, get_verified_user

router = APIRouter()

############################
# GetFunctions
############################


@router.get("/", response_model=list[FunctionResponse])
async def get_functions(user=Depends(get_verified_user)):
    return Functions.get_functions()


############################
# ExportFunctions
############################


@router.get("/export", response_model=list[FunctionModel])
async def get_functions(user=Depends(get_admin_user)):
    return Functions.get_functions()


############################
# CreateNewFunction
############################


@router.post("/create", response_model=Optional[FunctionResponse])
async def create_new_function(
    request: Request, form_data: FunctionForm, user=Depends(get_admin_user)
):
    if not form_data.id.isidentifier():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only alphanumeric characters and underscores are allowed in the id",
        )

    form_data.id = form_data.id.lower()

    function = Functions.get_function_by_id(form_data.id)
    if function is None:
        try:
            form_data.content = replace_imports(form_data.content)
            function_module, function_type, frontmatter = load_function_module_by_id(
                form_data.id,
                content=form_data.content,
            )
            form_data.meta.manifest = frontmatter

            FUNCTIONS = request.app.state.FUNCTIONS
            FUNCTIONS[form_data.id] = function_module

            function = Functions.insert_new_function(user.id, function_type, form_data)

            function_cache_dir = Path(CACHE_DIR) / "functions" / form_data.id
            function_cache_dir.mkdir(parents=True, exist_ok=True)

            if function:
                return function
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ERROR_MESSAGES.DEFAULT("Error creating function"),
                )
        except Exception as e:
            print(e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT(e),
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.ID_TAKEN,
        )


############################
# GetFunctionById
############################


@router.get("/id/{id}", response_model=Optional[FunctionModel])
async def get_function_by_id(id: str, user=Depends(get_admin_user)):
    function = Functions.get_function_by_id(id)

    if function:
        return function
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


############################
# ToggleFunctionById
############################


@router.post("/id/{id}/toggle", response_model=Optional[FunctionModel])
async def toggle_function_by_id(id: str, user=Depends(get_admin_user)):
    function = Functions.get_function_by_id(id)
    if function:
        function = Functions.update_function_by_id(
            id, {"is_active": not function.is_active}
        )

        if function:
            return function
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Error updating function"),
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


############################
# ToggleGlobalById
############################


@router.post("/id/{id}/toggle/global", response_model=Optional[FunctionModel])
async def toggle_global_by_id(id: str, user=Depends(get_admin_user)):
    function = Functions.get_function_by_id(id)
    if function:
        function = Functions.update_function_by_id(
            id, {"is_global": not function.is_global}
        )

        if function:
            return function
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Error updating function"),
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


############################
# UpdateFunctionById
############################


@router.post("/id/{id}/update", response_model=Optional[FunctionModel])
async def update_function_by_id(
    request: Request, id: str, form_data: FunctionForm, user=Depends(get_admin_user)
):
    try:
        form_data.content = replace_imports(form_data.content)
        function_module, function_type, frontmatter = load_function_module_by_id(
            id, content=form_data.content
        )
        form_data.meta.manifest = frontmatter

        FUNCTIONS = request.app.state.FUNCTIONS
        FUNCTIONS[id] = function_module

        updated = {**form_data.model_dump(exclude={"id"}), "type": function_type}
        print(updated)

        function = Functions.update_function_by_id(id, updated)

        if function:
            return function
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT("Error updating function"),
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(e),
        )


############################
# DeleteFunctionById
############################


@router.delete("/id/{id}/delete", response_model=bool)
async def delete_function_by_id(
    request: Request, id: str, user=Depends(get_admin_user)
):
    result = Functions.delete_function_by_id(id)

    if result:
        FUNCTIONS = request.app.state.FUNCTIONS
        if id in FUNCTIONS:
            del FUNCTIONS[id]

    return result


############################
# GetFunctionValves
############################


@router.get("/id/{id}/valves", response_model=Optional[dict])
async def get_function_valves_by_id(id: str, user=Depends(get_admin_user)):
    function = Functions.get_function_by_id(id)
    if function:
        try:
            valves = Functions.get_function_valves_by_id(id)
            return valves
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT(e),
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


############################
# GetFunctionValvesSpec
############################


@router.get("/id/{id}/valves/spec", response_model=Optional[dict])
async def get_function_valves_spec_by_id(
    request: Request, id: str, user=Depends(get_admin_user)
):
    function = Functions.get_function_by_id(id)
    if function:
        if id in request.app.state.FUNCTIONS:
            function_module = request.app.state.FUNCTIONS[id]
        else:
            function_module, function_type, frontmatter = load_function_module_by_id(id)
            request.app.state.FUNCTIONS[id] = function_module

        if hasattr(function_module, "Valves"):
            Valves = function_module.Valves
            return Valves.schema()
        return None
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


############################
# UpdateFunctionValves
############################


@router.post("/id/{id}/valves/update", response_model=Optional[dict])
async def update_function_valves_by_id(
    request: Request, id: str, form_data: dict, user=Depends(get_admin_user)
):
    function = Functions.get_function_by_id(id)
    if function:
        if id in request.app.state.FUNCTIONS:
            function_module = request.app.state.FUNCTIONS[id]
        else:
            function_module, function_type, frontmatter = load_function_module_by_id(id)
            request.app.state.FUNCTIONS[id] = function_module

        if hasattr(function_module, "Valves"):
            Valves = function_module.Valves

            try:
                form_data = {k: v for k, v in form_data.items() if v is not None}
                valves = Valves(**form_data)
                Functions.update_function_valves_by_id(id, valves.model_dump())
                return valves.model_dump()
            except Exception as e:
                print(e)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ERROR_MESSAGES.DEFAULT(e),
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ERROR_MESSAGES.NOT_FOUND,
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


############################
# FunctionUserValves
############################


@router.get("/id/{id}/valves/user", response_model=Optional[dict])
async def get_function_user_valves_by_id(id: str, user=Depends(get_verified_user)):
    function = Functions.get_function_by_id(id)
    if function:
        try:
            user_valves = Functions.get_user_valves_by_id_and_user_id(id, user.id)
            return user_valves
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ERROR_MESSAGES.DEFAULT(e),
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


@router.get("/id/{id}/valves/user/spec", response_model=Optional[dict])
async def get_function_user_valves_spec_by_id(
    request: Request, id: str, user=Depends(get_verified_user)
):
    function = Functions.get_function_by_id(id)
    if function:
        if id in request.app.state.FUNCTIONS:
            function_module = request.app.state.FUNCTIONS[id]
        else:
            function_module, function_type, frontmatter = load_function_module_by_id(id)
            request.app.state.FUNCTIONS[id] = function_module

        if hasattr(function_module, "UserValves"):
            UserValves = function_module.UserValves
            return UserValves.schema()
        return None
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )


@router.post("/id/{id}/valves/user/update", response_model=Optional[dict])
async def update_function_user_valves_by_id(
    request: Request, id: str, form_data: dict, user=Depends(get_verified_user)
):
    function = Functions.get_function_by_id(id)

    if function:
        if id in request.app.state.FUNCTIONS:
            function_module = request.app.state.FUNCTIONS[id]
        else:
            function_module, function_type, frontmatter = load_function_module_by_id(id)
            request.app.state.FUNCTIONS[id] = function_module

        if hasattr(function_module, "UserValves"):
            UserValves = function_module.UserValves

            try:
                form_data = {k: v for k, v in form_data.items() if v is not None}
                user_valves = UserValves(**form_data)
                Functions.update_user_valves_by_id_and_user_id(
                    id, user.id, user_valves.model_dump()
                )
                return user_valves.model_dump()
            except Exception as e:
                print(e)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=ERROR_MESSAGES.DEFAULT(e),
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=ERROR_MESSAGES.NOT_FOUND,
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

############################
# Helper Functions
############################

def _get_function_with_check(id: str) -> FunctionModel:
    """Helper to get function and validate it exists"""
    function = Functions.get_function_by_id(id)
    if not function:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    return function

def _get_update_url(function: FunctionModel) -> str:
    """Helper to get and validate update URL"""
    update_url = function.meta.manifest.get("update_url")
    if not update_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Update URL not found in function manifest",
        )
    return update_url

async def _fetch_and_check_version(function: FunctionModel) -> tuple[str, str, bool]:
    """Helper to fetch latest version and check if update needed"""
    try:
        response = requests.get(_get_update_url(function))
        response.raise_for_status()
        script = response.text
        frontmatter = extract_frontmatter(script)
        latest_version = frontmatter.get("version")
        current_version = function.meta.manifest.get("version")
        needs_update = latest_version and latest_version != current_version
        return script, latest_version, needs_update
    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error checking for updates: {str(e)}",
        )

############################
# API Endpoints
############################

@router.get("/id/{id}/check-updates", response_model=Optional[FunctionModel])
async def check_function_updates(id: str, user=Depends(get_admin_user)):
    function = _get_function_with_check(id)
    _, latest_version, needs_update = await _fetch_and_check_version(function)
    
    if needs_update:
        function.meta.manifest["update_available"] = True
        Functions.update_function_by_id(id, {"meta": function.meta})
        return function
    raise HTTPException(
        status_code=status.HTTP_200_OK,
        detail="No updates available",
    )

@router.get("/check-all-updates", response_model=list[FunctionModel])
async def check_all_function_updates(user=Depends(get_admin_user)):
    functions = Functions.get_functions()
    updated_functions = []

    for function in functions:
        if not function.meta.manifest.get("update_url"):
            continue
            
        try:
            _, _, needs_update = await _fetch_and_check_version(function)
            if needs_update:
                function_dump = function.model_dump()
                function_dump["meta"]["manifest"]["update_available"] = True
                updated_function = Functions.update_function_by_id(function.id, {"meta": function_dump["meta"]})
                updated_functions.append(updated_function)
        except HTTPException:
            print(f"Error checking updates for function {function.id}")
            continue

    return updated_functions

@router.post("/id/{id}/update-from-url", response_model=Optional[FunctionModel])
async def update_function_from_url(request: Request, id: str, user=Depends(get_admin_user)):
    function = _get_function_with_check(id)
    new_content, _, _ = await _fetch_and_check_version(function)
    
    form_data = FunctionForm(
        id=id,
        name=function.name,
        content=new_content,
        meta=function.meta
    )
    
    return await update_function_by_id(request, id, form_data, user)
