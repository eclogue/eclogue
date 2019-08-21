from eclogue.app import create_app
instance = create_app()

# instance.register_blueprint(main)


if __name__ == '__main__':
    instance.run(debug=True)
