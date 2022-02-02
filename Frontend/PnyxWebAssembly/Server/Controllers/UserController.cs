﻿using System;
using System.IO;
using Common.Data;
using Common.Entities;
using Common.Services;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Logging;

namespace PnyxWebAssembly.Server.Controllers
{
    [ApiController]
    [Route("User")]
    public class UserController : ControllerBase
    {
        /// <summary>
        /// The logger
        /// </summary>
        private readonly ILogger<UserController> _logger;

        /// <summary>
        /// Initializes a new instance of the <see cref="IssueController"/> class.
        /// </summary>
        /// <param name="logger">The logger.</param>
        public UserController(ILogger<UserController> logger)
        {
            _logger = logger;
        }

        /// <summary>
        /// Gets the user by external identifier.
        /// </summary>
        /// <param name="externalUserId">The external user identifier.</param>
        /// <returns>The user if found otherwise null</returns>
        [Authorize]
        [HttpGet("ByExternalId/{externalUserId}")]
        public IActionResult GetUserByExternalId(string externalUserId)
        {
            DbServiceContext dbServiceContext = DatabaseInitializationService.GetDbServiceContext();

            UserService userService = new UserService();

            using (dbServiceContext)
            {
                User user = userService.GetUserByExternalId(dbServiceContext, Guid.Parse(externalUserId));

                if (user == null)
                {
                    return NotFound();
                }

                _logger.LogInformation($"Get user by externalUserId {externalUserId}: {user}");

                return Ok(user);
            }
        }

        /// <summary>
        /// Gets the user by identifier.
        /// </summary>
        /// <param name="userId">The user identifier.</param>
        /// <returns>The user by id</returns>
        [Authorize]
        [HttpGet("ById/{userId}")]
        public IActionResult GetUserById(string userId)
        {
            DbServiceContext dbServiceContext = DatabaseInitializationService.GetDbServiceContext();

            UserService userService = new UserService();

            using (dbServiceContext)
            {
                User user = userService.GetUserById(dbServiceContext, Guid.Parse(userId));

                if (user == null)
                {
                    return NotFound();
                }

                _logger.LogInformation($"Get user by id {userId}: {user}");

                return Ok(user);
            }
        }

        /// <summary>
        /// Gets the user by user identifier.
        /// </summary>
        /// <param name="userName">Name of the user.</param>
        /// <returns>The user by the given name</returns>
        [Authorize]
        [HttpGet("ByName/{userName}")]
        public IActionResult GetUserByUserId(string userName)
        {
            DbServiceContext dbServiceContext = DatabaseInitializationService.GetDbServiceContext();

            UserService userService = new UserService();

            using (dbServiceContext)
            {
                User user = userService.GetUserByName(dbServiceContext, userName);

                if (user == null)
                {
                    return NotFound();
                }

                _logger.LogInformation($"Get user by name {userName}");

                return Ok(user);
            }
        }

        /// <summary>
        /// Creates the specified user.
        /// </summary>
        /// <param name="user">The user.</param>
        /// <returns>Ok if user creation was successful</returns>
        [Authorize]
        [HttpPost]
        public IActionResult Create([FromBody] User user)
        {
            DbServiceContext dbServiceContext = DatabaseInitializationService.GetDbServiceContext();

            using (dbServiceContext)
            {
                UserService userService = new UserService();

                userService.CreateUser(dbServiceContext, user, 100D);
                
                _logger.LogInformation($"Created user {user.UserName}");

                return Ok();
            }
        }

        /// <summary>
        /// Gets the avatar.
        /// </summary>
        /// <param name="userName">Name of the user.</param>
        /// <returns>The avatar image stream</returns>
        [HttpGet("Avatar/{userName}")]
        public IActionResult GetAvatar(string userName)
        {
            string path = GetPath(userName);

            if (!System.IO.File.Exists(path))
            {
                return NotFound();
            }

            _logger.LogInformation($"Get avatar for {userName}");

            return Ok(System.IO.File.Open(path, FileMode.Open, FileAccess.Read, FileShare.Read));
        }

        /// <summary>
        /// Gets the type of the avatar content.
        /// </summary>
        /// <param name="userName">Name of the user.</param>
        /// <returns>The avatar image type</returns>
        [HttpGet("AvatarContentType/{userName}")]
        public IActionResult GetAvatarContentType(string userName)
        {
            string path = GetPath(userName);

            if (!System.IO.File.Exists(path))
            {
                return NotFound();
            }

            string imageType = Path.GetExtension(path).Replace(".", string.Empty);

            _logger.LogInformation($"Get avatar content type for {userName}: {imageType}");

            return Ok(imageType);
        }

        /// <summary>
        /// Gets the path.
        /// </summary>
        /// <param name="userName">Name of the user.</param>
        /// <returns>The path to the avatar image file</returns>
        private string GetPath(string userName)
        {
            string imageName = $"{userName}.jpg".ToLowerInvariant();

            imageName = imageName.Replace("ä", "ae");
            imageName = imageName.Replace("ö", "oe");
            imageName = imageName.Replace("ü", "ue");
            imageName = imageName.Replace("ß", "ss");

            string path = @$"Images\Avatars\{imageName}";

            if (DatabaseInitializationService.IsDocker)
            {
                path = path.Replace("\\", "/");
            }

            if (!System.IO.File.Exists(path))
            {
                path = Path.ChangeExtension(path, "png");
            }

            _logger.LogInformation(!System.IO.File.Exists(path)
                ? $"Image {imageName} not found as avatar for user {userName}"
                : $"Image {path} found as avatar for user {userName}");

            return path;
        }
    }
}
